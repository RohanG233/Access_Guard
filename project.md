# AccessGuard — Project Explained Simply

> Already know MERN (MongoDB + Express + React + Node.js)?  
> This guide maps every file in this Python/Flask project to something you already understand.

---

## Stack Comparison at a Glance

| MERN | This Project (Flask) |
|---|---|
| Node.js + Express | Python + Flask |
| React / EJS templates | Jinja2 HTML templates |
| MongoDB + Mongoose | MongoDB + PyMongo |
| `routes/` + `controllers/` | All routes in `app.py` |
| `middleware/` or `utils/` | `utils/` package |
| `npm install` | `pip install -r requirements.txt` |
| `package.json` | `requirements.txt` |
| `.env` + `dotenv` | `.env` + `python-dotenv` (identical concept) |
| `node server.js` | `python app.py` |
| `pm2` / `node` in prod | `gunicorn` in prod |
| `public/` static folder | `static/` folder |
| `views/` EJS folder | `templates/` Jinja2 folder |

---

## Project Structure

```
AccessGuard/
│
├── app.py                          ← server.js + routes/ + controllers/ combined
│
├── utils/
│   ├── __init__.py                 ← makes utils/ a Python package (like index.js)
│   ├── encryption.py               ← utils/crypto.js equivalent
│   ├── face_recognition.py         ← services/faceService.js equivalent
│   └── voice_recognition.py        ← services/voiceService.js equivalent
│
├── templates/                      ← views/ folder (Jinja2 = EJS)
│   ├── base.html                   ← shared layout (header + footer + nav)
│   ├── index.html                  ← home page
│   ├── store.html                  ← registration form
│   ├── recognize.html              ← login / verify form
│   └── welcome.html                ← success page (auto-redirects after 10s)
│
├── static/                         ← public/ folder
│   ├── css/styles.css              ← all custom CSS
│   ├── js/scripts.js               ← all shared client-side JS
│   └── pexels-pavel-...jpg         ← background image
│
├── data/                           ← uploads/ equivalent (face + voice files)
├── plots/                          ← generated similarity histograms
├── log/                            ← audit log (app.log)
│
├── shape_predictor_68_face_landmarks.dat     ← pre-trained ML model file
├── dlib_face_recognition_resnet_model_v1.dat ← pre-trained ML model file
│
├── app.py
├── requirements.txt                ← package.json dependencies
├── .env.example                    ← .env template
├── .gitignore
├── Procfile                        ← deployment start command
├── README.md
└── project.md                      ← this file
```

---

## File-by-File Breakdown

---

### `app.py` — The Entire Backend

**MERN equivalent:** `server.js` + `routes/` + `controllers/` all in one file.

This is the core of the application. It does four things:

1. **Bootstraps the app** — loads `.env`, creates Flask app, connects to MongoDB, sets up logging, ensures `data/`, `log/`, `plots/` directories exist.

2. **Defines helper functions** — `generate_unique_user_id()`, `log_event()`, `save_similarity_plot()`.

3. **Defines all routes** — every URL the app responds to.

4. **Starts the server** — `app.run(...)` at the bottom.

**Express vs Flask syntax:**

```js
// Express
app.get('/', (req, res) => res.render('index'));
app.post('/store', (req, res) => {
    const name = req.body.name;
    res.redirect('/welcome');
});
```

```python
# Flask
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/store', methods=['POST'])
def store():
    name = request.form['name']
    return redirect(url_for('welcome'))
```

**Routes defined in `app.py`:**

| Route | Method | What it does |
|---|---|---|
| `/` | GET | Renders the home page |
| `/store` | GET | Shows the registration form |
| `/store` | POST | Saves face + voice + user data to disk and MongoDB |
| `/recognize` | GET | Shows the verify/login form |
| `/recognize` | POST | Runs biometric comparison, grants or denies access |
| `/welcome` | GET | Shows the success page (auto-redirects after 10s) |
| `/capture_face_data` | GET | Triggers webcam capture, returns base64 JPEG |
| `/capture_voice_data` | GET | Triggers mic recording, returns base64 WAV |

**Helper functions in `app.py`:**

- `generate_unique_user_id()` — generates a random 7-digit ID, checks MongoDB to ensure no collision, returns it.
- `log_event()` — thin wrapper around Python's `logging.info()`. Writes to `log/app.log`.
- `save_similarity_plot()` — reads previous scores from a `.txt` file, appends the new scores, saves a histogram PNG to `plots/`. Uses per-user files so scores survive server restarts (unlike a global in-memory list).

---

### `utils/__init__.py` — Package Marker

**MERN equivalent:** An `index.js` inside a folder that makes it importable.

Empty file. Its only job is to tell Python "this folder is a module". Without it, `from utils.encryption import ...` would fail.

---

### `utils/encryption.py` — AES Encryption Helper

**MERN equivalent:** A `utils/crypto.js` using Node's built-in `crypto` module.

```js
// Node equivalent concept
const crypto = require('crypto');
function encrypt(text) { /* ... */ }
function decrypt(text) { /* ... */ }
module.exports = { encrypt, decrypt };
```

**What it does:**

Exposes two functions — `encrypt_data(string)` and `decrypt_data(string)`.

- Uses **AES-EAX** mode — an authenticated encryption algorithm. This means it both encrypts the data (confidentiality) and signs it (integrity). If someone tampers with the ciphertext in MongoDB, decryption throws an error instead of silently returning garbage.
- The encryption key is derived from `ENCRYPTION_SECRET` in `.env` using SHA-256, truncated to 16 bytes.
- **What gets encrypted:** the file path strings stored in MongoDB (e.g. `data/1234567.jpg`). The actual biometric files live on disk. MongoDB never holds raw biometric data.

---

### `utils/face_recognition.py` — Face Comparison

**MERN equivalent:** A `services/faceService.js` that calls an ML library.

There's no direct Node equivalent — this is Python ML code. Conceptually it's the same as calling any service that returns a similarity score.

**Functions:**

- `get_face_encoding(image_rgb)` — takes an image array, runs it through the `face_recognition` library, returns a **128-number vector** (called an encoding). Think of it as a fingerprint made of 128 decimal numbers that uniquely describe a face.

- `calculate_similarity(stored_path, new_face_b64)` — loads the stored face from disk, decodes the new face from base64, gets the 128-d encoding for each, calculates the **Euclidean distance** between them, converts to similarity: `similarity = 1 - distance`. Returns a float between 0 and 1.

> Face capture now happens entirely in the browser via the webcam API (see `scripts.js`). The server only handles comparison.

**Why 128 numbers?** The `face_recognition` library uses a deep neural network (dlib's ResNet) trained on millions of faces. It learned to compress any face into exactly 128 numbers such that the same person's face always produces similar numbers, and different people produce different numbers.

---

### `utils/voice_recognition.py` — Voice Comparison

**MERN equivalent:** Same concept as `faceService.js` but for audio.

**Functions:**

- `capture_voice_data()` — records from the microphone using `SpeechRecognition`, saves to `data/temp.wav`, returns base64-encoded WAV. Local/desktop only.

- `_encode_voice(file_path)` — loads a WAV file with `librosa`, extracts **40 MFCC coefficients**. MFCC (Mel-Frequency Cepstral Coefficients) are 40 numbers that describe the unique tonal characteristics of a voice — pitch, resonance, speaking style. Think of it as a voice fingerprint.

- `calculate_voice_similarity(stored_path, new_voice_b64)` — decodes the new voice from base64, saves to temp file, extracts MFCCs for both, calculates **cosine similarity** between the two 40-number vectors. Returns a float between 0 and 1.

**Cosine similarity vs Euclidean distance:** Face uses Euclidean distance (straight-line distance between two points in 128-d space). Voice uses cosine similarity (angle between two vectors in 40-d space). Cosine is better for audio features because it's scale-invariant — it doesn't matter if you spoke loudly or quietly, only the shape of the voice pattern matters.

---

### `templates/base.html` — Shared Layout

**MERN equivalent:** A `layout.ejs` or `header.ejs` + `footer.ejs` that every page includes.

Contains the navbar, footer, Bootstrap CSS, Font Awesome icons, `styles.css`, and `scripts.js`. Every other template `extends` this file and fills in the `{% block content %}` section.

```html
<!-- Jinja2 inheritance -->
{% extends "base.html" %}
{% block content %}
  <h1>Page content here</h1>
{% endblock %}
```

```html
<!-- EJS equivalent -->
<%- include('header') %>
<h1>Page content here</h1>
<%- include('footer') %>
```

Also contains `<div id="alertContainer">` — the target for the `showAlert()` JS function.

---

### `templates/index.html` — Home Page

Two buttons: **Register** (→ `/store`) and **Verify Identity** (→ `/recognize`). Nothing else.

---

### `templates/store.html` — Registration Form

Collects: name, roll number, semester, PIN, face capture, voice capture.

The face and voice fields are `<input type="hidden">` — they hold base64 strings populated by JavaScript. The Submit button stays disabled until both captures succeed (enforced by `checkFormCompletion()` in `scripts.js`).

---

### `templates/recognize.html` — Verify / Login Form

Same structure as `store.html` but asks for User ID + PIN instead of personal details. Shows an error alert if the server returns one (wrong PIN, face mismatch, etc.).

---

### `templates/welcome.html` — Success Page

Shown after successful verification. Displays the user's name, roll number, and user ID. A JavaScript countdown from 10 automatically redirects to `/recognize` when it hits 0.

---

### `static/css/styles.css` — All Custom Styles

Supplements Bootstrap 4. Contains:
- Background image setup
- Navbar colour and hover animations
- Container card styling (white semi-transparent box)
- Fixed footer
- Pulsing animation for the "Recording..." indicator
- Status icon spacing

Previously some of these styles were inline in `base.html` — they've been consolidated here so there's one place to edit styles.

---

### `static/js/scripts.js` — All Shared Client-Side Logic

Previously duplicated inside both `store.html` and `recognize.html`. Now lives here and is loaded once by `base.html`.

Contains:
- `captureFaceData()` — opens a modal overlay with a live webcam preview in the browser. User clicks "Capture" to snapshot the frame. The image is drawn onto a canvas, converted to base64 JPEG, and stored in the hidden `#face_data` field. No server call needed — entirely client-side via the browser's `getUserMedia` API.
- `captureVoiceData()` — calls `/capture_voice_data`, shows pulsing "Recording..." indicator, stores result
- `checkFormCompletion()` — enables the Submit button only when both face and voice are captured
- `showAlert(message, type)` — injects a dismissible Bootstrap alert into `#alertContainer`

---

### `requirements.txt` — Dependency List

**MERN equivalent:** The `dependencies` block in `package.json`.

```
Flask          ← Express
pymongo        ← mongoose
python-dotenv  ← dotenv
pycryptodome   ← crypto (built-in in Node, external in Python)
face-recognition ← ML library for face encoding
opencv-python  ← image processing (reading/writing images)
librosa        ← audio feature extraction
scipy          ← cosine similarity math
SpeechRecognition ← mic recording
pyaudio        ← audio driver interface
matplotlib     ← chart/plot generation
scikit-learn   ← ML utilities
gunicorn       ← pm2 / production server
```

Install with: `pip install -r requirements.txt`

---

### `.env` / `.env.example` — Environment Variables

Identical concept to Node. Loaded with `load_dotenv()` in `app.py` (same as `require('dotenv').config()`).

| Variable | Required? | Purpose | Default |
|---|---|---|---|
| `FLASK_SECRET_KEY` | **Yes** | Signs session cookies (like `JWT_SECRET` in Express) | Random (lost on restart) |
| `MONGO_URI` | **Yes** | MongoDB connection string | `mongodb://localhost:27017/` |
| `MONGO_DB_NAME` | No | Database name | `user_database` |
| `ENCRYPTION_SECRET` | **Yes** | AES key source for encrypting file paths in MongoDB | Insecure default |
| `FLASK_ENV` | No | `development` or `production` | `development` |
| `FLASK_DEBUG` | No | `1` = debug on, `0` = off | `1` |
| `PORT` | No | Port to run on | `5000` |

**The three you must set before running:**

```bash
# 1. Copy the template
cp .env.example .env

# 2. Generate FLASK_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Generate ENCRYPTION_SECRET
python -c "import secrets; print(secrets.token_hex(32))"

# 4. Set MONGO_URI
# Local:  mongodb://localhost:27017/
# Atlas:  mongodb+srv://<user>:<pass>@cluster.mongodb.net/
```

> ⚠️ Never change `ENCRYPTION_SECRET` after users have registered. It derives the AES key — changing it makes all existing encrypted paths in MongoDB unreadable and locks out existing users.

---

### `Procfile` — Production Start Command

**MERN equivalent:** `"start": "node server.js"` in `package.json`.

```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

`gunicorn` is the production WSGI server (like using `pm2` with Node). The Flask dev server (`python app.py`) is single-threaded and not safe for production.

---

### `dlib_face_recognition_resnet_model_v1.dat` and `shape_predictor_68_face_landmarks.dat`

Pre-trained neural network weight files used internally by the `face_recognition` library. ~100 MB each. Downloaded separately and not committed to git. No MERN equivalent — these are ML-specific binary assets.

**`dlib_face_recognition_resnet_model_v1.dat`** — the actual deep learning model. A ResNet trained on ~3 million face images. Takes a face image, outputs a 128-number vector (embedding) that uniquely represents that face. Used at both registration and login.

**`shape_predictor_68_face_landmarks.dat`** — detects 68 landmark points on a face (corners of eyes, tip of nose, jawline etc.) to align the face before encoding. Required by the ResNet model for accurate results.

Neither file is trained or updated by this project. They are fixed inference-only weights.

**Is this AI?** The face part yes — it uses a genuine pre-trained deep neural network. The voice part (MFCC + cosine similarity) is classical signal processing, not AI. No training happens at runtime.

---

### `data/` — Biometric File Storage

**MERN equivalent:** `uploads/` folder (like Multer file storage in Express).

Stores:
- `<user_id>.jpg` — registered face image
- `<user_id>.wav` — registered voice sample
- `temp.wav` — temporary file used during voice comparison

Created automatically at startup. Git-ignored.

---

### `plots/` — Similarity Score Charts

Generated at runtime. After every recognition attempt, a histogram of face and voice similarity scores is saved as `<user_id>.png`. Also stores `<user_id>.txt` with the raw score history (one `face,voice` pair per line) so charts survive server restarts. Git-ignored.

---

### `log/app.log` — Audit Trail

Every event is logged here with a timestamp:
- `Registration` — new user enrolled
- `Success` — user verified successfully
- `Failed Auth` — wrong PIN, face mismatch, or voice mismatch

**MERN equivalent:** Winston or Morgan log output. Git-ignored.

---

## Full Request Flow — Registration

```
1. GET /store
   Flask → render_template('store.html') → browser shows form

2. User clicks "Capture Face"
   JS → fetch('/capture_face_data')
   Flask → opens webcam → user presses S → returns base64 JPEG
   JS → stores in hidden #face_data field, shows ✔

3. User clicks "Capture Voice"
   JS → fetch('/capture_voice_data')
   Flask → records mic → returns base64 WAV
   JS → stores in hidden #voice_data field, shows ✔
   JS → checkFormCompletion() → enables Submit button

4. User clicks Submit
   Browser → POST /store (form data including base64 blobs)

5. Flask /store handler:
   ├── decode base64 face  → write data/1234567.jpg
   ├── decode base64 voice → write data/1234567.wav
   ├── encrypt_data("data/1234567.jpg") → AES ciphertext
   ├── encrypt_data("data/1234567.wav") → AES ciphertext
   ├── collection.insert_one({ user_id, name, rollno, ... })
   └── redirect → /welcome?user_id=1234567&name=...

6. GET /welcome
   Flask → render_template('welcome.html', ...)
   JS countdown → 10 seconds → redirect to /recognize
```

---

## Full Request Flow — Verification (Login)

```
1. GET /recognize
   Flask → render_template('recognize.html')

2. User enters user_id + PIN, captures face + voice
   → POST /recognize

3. Flask /recognize handler:
   ├── collection.find_one({ user_id }) → check PIN
   │     FAIL → render recognize.html with error
   │
   ├── decrypt_data(user['face_data'])  → "data/1234567.jpg"
   ├── decrypt_data(user['voice_data']) → "data/1234567.wav"
   │
   ├── calculate_similarity("data/1234567.jpg", new_face_b64)
   │     → load both images → 128-d encodings → distance → score
   │
   ├── calculate_voice_similarity("data/1234567.wav", new_voice_b64)
   │     → load both WAVs → 40 MFCCs → cosine similarity → score
   │
   ├── face_score >= 50% AND voice_score >= 60%?
   │     YES → log_event("Success") → redirect /welcome
   │     NO  → log_event("Failed Auth") → render recognize.html with error
   │
   └── save_similarity_plot(user_id, face_score, voice_score)
```

---

## Summary Table

| Concept | MERN | This Project |
|---|---|---|
| Start server | `node server.js` | `python app.py` |
| Install packages | `npm install` | `pip install -r requirements.txt` |
| Define GET route | `app.get('/path', fn)` | `@app.route('/path')` |
| Define POST route | `app.post('/path', fn)` | `@app.route('/path', methods=['POST'])` |
| Read POST body | `req.body.field` | `request.form['field']` |
| Render HTML | `res.render('view', data)` | `render_template('view.html', **data)` |
| Send JSON | `res.json({...})` | `jsonify({...})` |
| Redirect | `res.redirect('/path')` | `redirect(url_for('route_fn'))` |
| DB find one | `Model.findOne({...})` | `collection.find_one({...})` |
| DB insert | `Model.create({...})` | `collection.insert_one({...})` |
| Env vars | `process.env.KEY` | `os.environ.get('KEY')` |
| Shared layout | EJS partials | Jinja2 `extends` + `block` |
| Template variable | `<%= variable %>` | `{{ variable }}` |
| Template if | `<% if (x) { %>` | `{% if x %}` |
| Template loop | `<% for (x of arr) { %>` | `{% for x in arr %}` |
| Static files | `express.static('public')` | Flask serves `static/` automatically |
| Helper modules | `utils/helper.js` | `utils/helper.py` |
| Make folder a module | `index.js` in folder | `__init__.py` in folder |
| Production server | `pm2` / `node` | `gunicorn` |
| Deployment config | `scripts.start` in package.json | `Procfile` |

---

## File & Folder Connection Map

This section explains every file and folder — what it does, what it talks to, and how those connections work.

---

### Connection Overview (Bird's Eye)

```
Browser
  │
  │  HTTP requests (GET/POST)
  ▼
app.py  ◄──── .env (config/secrets)
  │
  ├── utils/encryption.py       (PIN hashing + AES for legacy data)
  ├── utils/face_recognition.py (face encoding + similarity)
  ├── utils/voice_recognition.py(voice encoding + similarity)
  │
  ├── templates/*.html          (rendered HTML sent back to browser)
  │     └── base.html           (shared layout, loaded by all pages)
  │
  ├── static/css/styles.css     (loaded by base.html in browser)
  ├── static/js/scripts.js      (loaded by base.html in browser)
  │
  ├── MongoDB (user_data collection)
  │     └── stores: user_id, name, rollno, semester,
  │                 pin_hash, face_data (Binary), voice_data (Binary)
  │
  ├── plots/  (PNG + TXT files written by app.py after each login)
  └── log/    (app.log written by app.py on every event)

dlib_face_recognition_resnet_model_v1.dat  ◄── used by face_recognition library
shape_predictor_68_face_landmarks.dat      ◄── used by face_recognition library
```

---

### Root Files

#### `app.py`
The entire backend. Every URL route, every piece of business logic, and all wiring between components lives here.

Connects to:
- `.env` — reads all config at startup via `load_dotenv()`
- `utils/encryption.py` — calls `encrypt_data()` / `decrypt_data()` for PIN handling
- `utils/face_recognition.py` — calls `calculate_similarity()` during login
- `utils/voice_recognition.py` — calls `calculate_voice_similarity()` and `capture_voice_data()`
- `templates/*.html` — renders them via `render_template()`
- MongoDB — reads and writes user records via PyMongo `collection`
- `plots/` — writes similarity score history files and PNG charts
- `log/app.log` — writes every auth event (registration, success, failure)

How the connection works: Flask decorators (`@app.route`) map URLs to Python functions. When a request arrives, the matching function runs, calls utils as needed, reads/writes MongoDB, then returns either a rendered HTML page or a redirect.

---

#### `requirements.txt`
Lists every Python package the project depends on with pinned versions.

Connects to:
- Nothing at runtime — it's only read by `pip install -r requirements.txt` during setup.
- Indirectly enables everything: without it, `app.py` and all utils would fail to import.

---

#### `.env`
Holds all secrets and environment-specific config (MongoDB URI, secret keys, thresholds).

Connects to:
- `app.py` — read at startup via `load_dotenv()`, then accessed with `os.environ.get()`
- `utils/encryption.py` — reads `ENCRYPTION_SECRET` at import time to derive the AES key

How the connection works: `load_dotenv()` in `app.py` loads the file into `os.environ` before any other import runs. This means by the time `utils/encryption.py` is imported, `ENCRYPTION_SECRET` is already in the environment.

---

#### `.env.example`
A safe template of `.env` with placeholder values. Committed to git; `.env` is not.

Connects to: nothing at runtime. It's documentation for anyone setting up the project.

---

#### `Procfile`
Tells Gunicorn how to start the app in production: `web: gunicorn app:app ...`

Connects to:
- `app.py` — `app:app` means "the `app` object inside `app.py`"
- Used by Heroku, Railway, and similar platforms to start the server

---

#### `startup.log` / `startup_err.log`
Stdout and stderr captured when the app starts on a hosted platform (e.g. Railway).

Connects to: nothing in code. Written by the platform's process runner, not by the app itself.

---

### `utils/` folder

Makes the utils a Python package. `app.py` imports from it with `from utils.X import Y`.

---

#### `utils/__init__.py`
Empty file. Its only job is to mark `utils/` as a Python package so imports work.

Connects to: nothing directly. Without it, `from utils.encryption import ...` would raise an ImportError.

---

#### `utils/encryption.py`
Handles AES-EAX encryption and decryption for any string data stored in MongoDB.

Connects to:
- `.env` — reads `ENCRYPTION_SECRET` at import time to build the AES key
- `app.py` — `encrypt_data()` called when storing a PIN, `decrypt_data()` called when verifying

How the connection works: the key is derived once at module load time (`SECRET_KEY = hashlib.sha256(...).digest()[:16]`). Every call to `encrypt_data` / `decrypt_data` uses that cached key. No file I/O at call time — pure in-memory crypto.

---

#### `utils/face_recognition.py`
Converts face images to 128-dimensional vectors and computes similarity between two faces.

Connects to:
- `dlib_face_recognition_resnet_model_v1.dat` — loaded automatically by the `face_recognition` library when the module is first used
- `shape_predictor_68_face_landmarks.dat` — also loaded by `face_recognition` for landmark detection
- `app.py` — `calculate_similarity(stored_bytes, new_b64)` called during login

How the connection works: `app.py` passes raw face bytes (from MongoDB) and a base64 string (from the login form). This module decodes both to RGB arrays, runs them through dlib's ResNet to get 128-number vectors, then returns `1 - euclidean_distance` as the similarity score.

---

#### `utils/voice_recognition.py`
Extracts 40 MFCC coefficients from WAV audio and computes cosine similarity between two voice samples.

Connects to:
- `app.py` — `calculate_voice_similarity(stored_bytes, new_b64)` called during login; `capture_voice_data()` called by the `/capture_voice_data` route
- No model files — MFCC is pure signal processing via `librosa`

How the connection works: `app.py` passes raw voice bytes (from MongoDB) and a base64 WAV string (from the login form). This module decodes both, extracts MFCC vectors, and returns cosine similarity. `capture_voice_data()` records from the server microphone and returns a base64 WAV string.

---

### `templates/` folder

All HTML pages. Flask's `render_template()` in `app.py` picks the right file, injects variables, and sends the result to the browser.

---

#### `templates/base.html`
The shared layout. Every other template extends this.

Connects to:
- All other templates — they use `{% extends "base.html" %}` and fill `{% block content %}`
- `static/css/styles.css` — linked via `<link>` tag
- `static/js/scripts.js` — linked via `<script>` tag
- Bootstrap 4 and Font Awesome — loaded from CDN with SRI integrity hashes

How the connection works: Jinja2 template inheritance. `base.html` defines the skeleton (navbar, footer, CSS/JS links). Child templates slot their content into `{% block content %}`. Flask renders the final merged HTML and sends it to the browser.

---

#### `templates/index.html`
The home/landing page. Two buttons: Register and Verify.

Connects to:
- `base.html` — extends it
- `app.py` — rendered by the `index()` route (`GET /`)
- Links to `/store` and `/recognize` routes

---

#### `templates/store.html`
The registration form. Collects name, roll number, semester, PIN, face scan, and voice sample.

Connects to:
- `base.html` — extends it
- `app.py` — rendered by `store()` on `GET /store`; form POSTs to `POST /store`
- `static/js/scripts.js` — `captureFaceData()` and `captureVoiceData()` called by buttons on this page
- Hidden inputs `#face_data` and `#voice_data` are populated by JS before form submission

---

#### `templates/recognize.html`
The login/verification form. Collects user ID, PIN, face scan, and voice sample.

Connects to:
- `base.html` — extends it
- `app.py` — rendered by `recognize()` on `GET /recognize`; form POSTs to `POST /recognize`
- `static/js/scripts.js` — same face/voice capture functions as store.html

---

#### `templates/welcome.html`
The success page shown after registration or login.

Connects to:
- `base.html` — extends it
- `app.py` — rendered by `welcome()` route; receives `user_id`, `name`, `rollno`, `source` as URL params
- JS countdown redirects to `/` (after registration) or `/recognize` (after login) based on `source`

---

### `static/` folder

Files served directly to the browser by Flask. No server-side processing.

---

#### `static/css/styles.css`
All custom CSS — supplements Bootstrap. Styles the navbar, cards, capture buttons, countdown bar, status indicators.

Connects to:
- `templates/base.html` — loaded via `<link>` tag on every page
- No Python connection — pure browser-side

---

#### `static/js/scripts.js`
All shared client-side JavaScript.

Connects to:
- `templates/base.html` — loaded via `<script>` tag on every page
- `templates/store.html` and `templates/recognize.html` — buttons on these pages call functions defined here
- `app.py` route `/capture_voice_data` — `captureVoiceData()` makes a `fetch()` GET request to this endpoint
- Browser webcam API (`navigator.mediaDevices.getUserMedia`) — `captureFaceData()` opens the camera directly in the browser, no server call needed

How the connection works: `captureFaceData()` captures a frame from the webcam, draws it on a canvas, converts to base64 JPEG, and writes it into the hidden `#face_data` input. `captureVoiceData()` calls the server endpoint which records from the server mic and returns base64 WAV, written into `#voice_data`. The form submit button stays disabled until both fields are filled (`checkFormCompletion()`).

---

### `data/` folder

Temporary storage for voice recordings during capture. Created at startup if missing.

Connects to:
- `utils/voice_recognition.py` — `capture_voice_data()` previously wrote `temp.wav` here (now in-memory)
- Git-ignored — never committed

---

### `plots/` folder

Runtime-generated similarity score charts. Created at startup if missing.

Connects to:
- `app.py` — `save_similarity_plot()` writes `<user_id>.txt` (raw scores) and `<user_id>.png` (histogram) here after every login attempt
- Git-ignored — never committed

---

### `log/` folder

Audit trail for all auth events.

Connects to:
- `app.py` — `log_event()` writes to `log/app.log` on every registration, successful login, and failed login attempt
- Git-ignored — never committed

---

### Model files (root)

#### `dlib_face_recognition_resnet_model_v1.dat`
Pre-trained ResNet neural network weights (~100 MB). Converts a face image to a 128-number vector.

Connects to:
- `utils/face_recognition.py` — loaded automatically by the `face_recognition` library when `face_encodings()` is first called
- Not imported directly in any Python file — the `face_recognition` library handles loading it

#### `shape_predictor_68_face_landmarks.dat`
Pre-trained landmark detector (~100 MB). Finds 68 key points on a face (eyes, nose, jaw) to align it before encoding.

Connects to:
- `utils/face_recognition.py` — same as above, loaded automatically by `face_recognition`
- Must be in the working directory or on dlib's search path

---

### MongoDB (external)

Not a file in the repo, but a critical connection point.

Connects to:
- `app.py` — all reads and writes go through the `collection` object (PyMongo)
- Stores one document per user: `user_id`, `name`, `rollno`, `semester`, `pin_hash`, `face_data` (Binary), `voice_data` (Binary)
- URI configured via `MONGO_URI` in `.env`

---

### Connection Summary Table

| File / Folder | Talks To | How |
|---|---|---|
| `app.py` | `.env`, all utils, all templates, MongoDB, `plots/`, `log/` | imports, render_template, PyMongo |
| `utils/encryption.py` | `.env` | `os.environ.get` at import time |
| `utils/face_recognition.py` | dlib `.dat` files, `app.py` | library auto-load, function call |
| `utils/voice_recognition.py` | `app.py` | function call |
| `templates/base.html` | all templates, `static/css`, `static/js`, CDN | Jinja2 inheritance, `<link>`, `<script>` |
| `templates/store.html` | `base.html`, `app.py`, `scripts.js` | extends, POST form, JS function calls |
| `templates/recognize.html` | `base.html`, `app.py`, `scripts.js` | extends, POST form, JS function calls |
| `templates/welcome.html` | `base.html`, `app.py` | extends, URL params from redirect |
| `static/js/scripts.js` | `/capture_voice_data` route, browser webcam API | fetch(), getUserMedia() |
| `static/css/styles.css` | browser only | loaded by base.html |
| `Procfile` | `app.py` | gunicorn entry point |
| `.env` | `app.py`, `utils/encryption.py` | `load_dotenv()` + `os.environ` |
| `plots/` | `app.py` | file write after each login |
| `log/` | `app.py` | logging module |
| MongoDB | `app.py` | PyMongo over TCP |
| `.dat` model files | `utils/face_recognition.py` | dlib auto-discovery |
