import os
import logging
import random
import base64
import secrets
import re
import uuid

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import bcrypt

from flask import Flask, render_template, request, redirect, url_for, jsonify, g
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import Binary
from dotenv import load_dotenv

from utils.encryption import encrypt_data, decrypt_data
from utils.face_recognition import calculate_similarity
from utils.voice_recognition import capture_voice_data, calculate_voice_similarity

# ── Bootstrap ─────────────────────────────────────────────────────────────────
load_dotenv()

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config['WTF_CSRF_ENABLED'] = True
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64 MB

# Security headers
app.config['SESSION_COOKIE_SECURE']   = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# CSRF
csrf = CSRFProtect(app)

# Rate limiter — keyed by IP
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

# Ensure runtime directories exist
for _dir in ('log', 'plots'):
    os.makedirs(os.path.join(_BASE_DIR, _dir), exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
_log_file = os.path.join(_BASE_DIR, 'log', 'app.log')
_access_log_file = os.path.join(_BASE_DIR, 'log', 'access.log')

logging.basicConfig(
    filename=_log_file,
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [%(request_id)s] %(message)s'
)

# Dedicated access logger — successful logins only
_access_logger = logging.getLogger('access')
_access_logger.setLevel(logging.INFO)
_access_logger.propagate = False  # don't bleed into app.log
_access_handler = logging.FileHandler(_access_log_file)
_access_handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
_access_logger.addHandler(_access_handler)

class _RequestIdFilter(logging.Filter):
    def filter(self, record):
        try:
            record.request_id = getattr(g, 'request_id', '-')
        except RuntimeError:
            record.request_id = '-'
        return True

for handler in logging.root.handlers:
    handler.addFilter(_RequestIdFilter())

logger = logging.getLogger(__name__)

# ── MongoDB ───────────────────────────────────────────────────────────────────
_mongo_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
_db_name   = os.environ.get('MONGO_DB_NAME', 'user_database')

try:
    _client = MongoClient(_mongo_uri, serverSelectionTimeoutMS=5000)
    _client.admin.command('ping')  # fail fast if unreachable
    logger.info("MongoDB connected: %s / %s", _mongo_uri.split('@')[-1], _db_name)
except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
    raise SystemExit(f"[FATAL] Cannot connect to MongoDB: {exc}") from exc

_db        = _client[_db_name]
collection = _db['user_data']

# Ensure indexes (idempotent)
collection.create_index([('user_id', ASCENDING)], unique=True)
collection.create_index([('rollno', ASCENDING)])

# ── Thresholds (configurable via env) ─────────────────────────────────────────
THRESHOLD_FACE  = float(os.environ.get('THRESHOLD_FACE',  '50.0'))
THRESHOLD_VOICE = float(os.environ.get('THRESHOLD_VOICE', '60.0'))

# ── Input validation constants ────────────────────────────────────────────────
_NAME_RE   = re.compile(r"^[A-Za-z\s\.\-']{2,80}$")
_ROLLNO_RE = re.compile(r"^[A-Za-z0-9\-/]{2,20}$")
_SEM_RE    = re.compile(r"^[1-9]$|^10$")
_PIN_RE    = re.compile(r"^\d{4,12}$")
_UID_RE    = re.compile(r"^\d{7}$")

# Max decoded bytes for biometric payloads
_MAX_FACE_BYTES  = 5 * 1024 * 1024   # 5 MB
_MAX_VOICE_BYTES = 10 * 1024 * 1024  # 10 MB

# ── Request ID middleware ─────────────────────────────────────────────────────
@app.before_request
def _assign_request_id():
    g.request_id = str(uuid.uuid4())[:8]

@app.after_request
def _security_headers(response):
    env = os.environ.get('FLASK_ENV', 'development')
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']        = 'DENY'
    response.headers['X-XSS-Protection']       = '1; mode=block'
    response.headers['Referrer-Policy']        = 'strict-origin-when-cross-origin'
    if env == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_unique_user_id() -> str:
    """Return a collision-free 7-digit user ID using a cryptographically secure RNG."""
    for _ in range(20):  # bounded loop — avoids infinite loop on near-full ID space
        uid = str(secrets.randbelow(9000000) + 1000000)
        if not collection.find_one({'user_id': uid}):
            return uid
    raise RuntimeError("Could not generate a unique user ID after 20 attempts.")


def log_event(event: str, user_id: str, details: str = "") -> None:
    logger.info("Event=%s user=%s %s", event, user_id, details)


def log_access(user_id: str, name: str, rollno: str, face_score: float, voice_score: float) -> None:
    """Write a structured entry to access.log for every successful verification."""
    _access_logger.info(
        "ACCESS_GRANTED | user_id=%-8s | name=%-20s | rollno=%-10s | face=%5.1f%% | voice=%5.1f%%",
        user_id, name, rollno, face_score, voice_score
    )


def save_similarity_plot(user_id: str, face_score: float, voice_score: float) -> None:
    score_file = os.path.join(_BASE_DIR, 'plots', f'{user_id}.txt')
    scores = []
    if os.path.exists(score_file):
        with open(score_file) as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) == 2:
                    try:
                        scores.append((float(parts[0]), float(parts[1])))
                    except ValueError:
                        pass
    scores.append((face_score, voice_score))
    with open(score_file, 'w') as f:
        for fs, vs in scores:
            f.write(f'{fs},{vs}\n')

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist([s[0] for s in scores], bins=10, alpha=0.5, label='Face Similarity')
    ax.hist([s[1] for s in scores], bins=10, alpha=0.5, label='Voice Similarity')
    ax.set_title('Distribution of Similarity Scores')
    ax.set_xlabel('Similarity Score (%)')
    ax.set_ylabel('Frequency')
    ax.legend(loc='upper right')
    ax.grid(True)
    fig.savefig(os.path.join(_BASE_DIR, 'plots', f'{user_id}.png'))
    plt.close(fig)


def _validate_biometric_b64(b64_str: str, max_bytes: int, label: str) -> bytes:
    """Decode and size-check a base64 biometric payload. Raises ValueError on failure."""
    try:
        raw = base64.b64decode(b64_str)
    except Exception:
        raise ValueError(f"Invalid base64 for {label}.")
    if len(raw) > max_bytes:
        raise ValueError(f"{label} payload too large ({len(raw)} bytes, max {max_bytes}).")
    if len(raw) < 1024:
        raise ValueError(f"{label} payload too small — capture may have failed.")
    return raw


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/store', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def store():
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        rollno   = request.form.get('rollno', '').strip()
        semester = request.form.get('semester', '').strip()
        pincode  = request.form.get('pincode', '').strip()
        face_b64 = request.form.get('face_data', '').strip()
        voice_b64 = request.form.get('voice_data', '').strip()

        # Input validation
        errors = []
        if not _NAME_RE.match(name):
            errors.append("Name must be 2–80 letters.")
        if not _ROLLNO_RE.match(rollno):
            errors.append("Roll number must be 2–20 alphanumeric characters.")
        if not _SEM_RE.match(semester):
            errors.append("Semester must be 1–10.")
        if not _PIN_RE.match(pincode):
            errors.append("PIN must be 4–12 digits.")
        if errors:
            return render_template('store.html', error=" | ".join(errors))

        try:
            face_bytes  = _validate_biometric_b64(face_b64,  _MAX_FACE_BYTES,  "Face")
            voice_bytes = _validate_biometric_b64(voice_b64, _MAX_VOICE_BYTES, "Voice")
        except ValueError as exc:
            return render_template('store.html', error=str(exc))

        # Check for duplicate roll number
        if collection.find_one({'rollno': rollno}):
            return render_template('store.html', error="User already exists")

        # Hash PIN with bcrypt (never store plaintext or reversibly encrypted PINs)
        pin_hash = bcrypt.hashpw(pincode.encode(), bcrypt.gensalt()).decode()

        user_id = generate_unique_user_id()

        collection.insert_one({
            'user_id':    user_id,
            'name':       name,
            'rollno':     rollno,
            'semester':   semester,
            'pin_hash':   pin_hash,
            'face_data':  Binary(face_bytes),
            'voice_data': Binary(voice_bytes),
        })
        log_event("Registration", user_id, f"name={name} roll={rollno}")
        return redirect(url_for('welcome', user_id=user_id, name=name, rollno=rollno, source='register'))

    return render_template('store.html')


@app.route('/recognize', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def recognize():
    if request.method == 'POST':
        user_id   = request.form.get('user_id', '').strip()
        pincode   = request.form.get('pincode', '').strip()
        face_b64  = request.form.get('face_data', '').strip()
        voice_b64 = request.form.get('voice_data', '').strip()

        # Validate user_id and PIN format before hitting DB
        if not _UID_RE.match(user_id) or not _PIN_RE.match(pincode):
            msg = "Invalid credentials."
            log_event("Failed Auth", user_id or "?", "bad input format")
            return render_template('recognize.html', error=msg)

        try:
            face_bytes_new  = _validate_biometric_b64(face_b64,  _MAX_FACE_BYTES,  "Face")
            voice_bytes_new = _validate_biometric_b64(voice_b64, _MAX_VOICE_BYTES, "Voice")
        except ValueError as exc:
            return render_template('recognize.html', error=str(exc))

        user = collection.find_one({'user_id': user_id})

        # User not found
        if not user:
            log_event("Failed Auth", user_id, "user not found")
            return render_template('recognize.html',
                                   error_type='userid',
                                   error="User ID does not exist.")

        # Constant-time PIN check
        _dummy_hash = b'$2b$12$invalidhashpadding000000000000000000000000000000000000'
        stored_hash = user['pin_hash'].encode() if user.get('pin_hash') else _dummy_hash
        pin_ok = bcrypt.checkpw(pincode.encode(), stored_hash)

        if not pin_ok:
            log_event("Failed Auth", user_id, "wrong PIN")
            return render_template('recognize.html',
                                   error_type='pin',
                                   error="Wrong PIN. Please try again.")

        face_bytes  = bytes(user['face_data'])
        voice_bytes = bytes(user['voice_data'])

        face_score  = calculate_similarity(face_bytes, face_b64) * 100
        voice_score = calculate_voice_similarity(voice_bytes, voice_b64) * 100

        logger.info("Scores for user %s — face=%.1f%% voice=%.1f%%", user_id, face_score, voice_score)

        save_similarity_plot(user_id, face_score, voice_score)

        if face_score >= THRESHOLD_FACE and voice_score >= THRESHOLD_VOICE:
            log_event("Success", user_id,
                      f"face={face_score:.1f}% voice={voice_score:.1f}%")
            log_access(user_id, user['name'], user['rollno'], face_score, voice_score)
            return redirect(url_for('welcome',
                                    user_id=user_id,
                                    name=user['name'],
                                    rollno=user['rollno'],
                                    source='login'))

        # At least one biometric must pass
        face_pass  = face_score  >= THRESHOLD_FACE
        voice_pass = voice_score >= THRESHOLD_VOICE

        if face_pass or voice_pass:
            log_event("Success", user_id,
                      f"face={face_score:.1f}% voice={voice_score:.1f}% (partial)")
            log_access(user_id, user['name'], user['rollno'], face_score, voice_score)
            return redirect(url_for('welcome',
                                    user_id=user_id,
                                    name=user['name'],
                                    rollno=user['rollno'],
                                    source='login'))

        log_event("Failed Auth", user_id,
                  f"face={face_score:.1f}% voice={voice_score:.1f}%")
        return render_template('recognize.html',
                               error_type='biometric',
                               face_score=round(face_score, 1),
                               voice_score=round(voice_score, 1),
                               face_threshold=THRESHOLD_FACE,
                               voice_threshold=THRESHOLD_VOICE)

    return render_template('recognize.html')


@app.route('/welcome')
def welcome():
    return render_template('welcome.html',
                           user_id=request.args.get('user_id'),
                           name=request.args.get('name'),
                           rollno=request.args.get('rollno'),
                           source=request.args.get('source', 'login'))


@app.route('/capture_voice_data')
@limiter.limit("20 per minute")
@csrf.exempt
def capture_voice():
    data = capture_voice_data()
    return jsonify({'success': bool(data), 'voice_data': data or ''})


@app.route('/health')
@csrf.exempt
def health():
    """Health check endpoint for load balancers / orchestrators."""
    try:
        _client.admin.command('ping')
        return jsonify({'status': 'ok', 'db': 'connected'}), 200
    except Exception:
        return jsonify({'status': 'error', 'db': 'unreachable'}), 503


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(413)
def request_too_large(e):
    # Stay on whichever page triggered the upload
    if request.path.startswith('/store') or request.referrer and '/store' in request.referrer:
        return render_template('store.html', error="Upload too large. Please try again."), 413
    return render_template('recognize.html', error="Upload too large. Please try again."), 413


@app.errorhandler(429)
def rate_limited(e):
    if request.path.startswith('/store') or request.referrer and '/store' in request.referrer:
        return render_template('store.html', error="Too many attempts. Please wait and try again."), 429
    return render_template('recognize.html', error="Too many attempts. Please wait and try again."), 429


@app.errorhandler(CSRFError)
def csrf_error(e):
    if request.path.startswith('/store') or request.referrer and '/store' in request.referrer:
        return render_template('store.html', error="Session expired. Please refresh and try again."), 400
    return render_template('recognize.html', error="Session expired. Please refresh and try again."), 400


@app.errorhandler(500)
def internal_error(e):
    logger.error("Unhandled exception: %s", e, exc_info=True)
    if request.path.startswith('/store'):
        return render_template('store.html', error="An unexpected error occurred. Please try again."), 500
    if request.path.startswith('/recognize'):
        return render_template('recognize.html', error="An unexpected error occurred. Please try again."), 500
    return render_template('index.html'), 500


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(
        debug=debug,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000))
    )
