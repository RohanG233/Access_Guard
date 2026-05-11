# AccessGuard (PIMFALE)

A biometric identity verification system that authenticates users using **face recognition + voice recognition + PIN**, built with Python/Flask and MongoDB.

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask 3.x |
| Frontend | Jinja2 templates, Bootstrap 4, Vanilla JS |
| Database | MongoDB (PyMongo) |
| Face Recognition | face-recognition (dlib ResNet under the hood), OpenCV |
| Voice Recognition | librosa (MFCC features), SpeechRecognition, PyAudio |
| Encryption | AES-EAX (PyCryptodome) |
| Plotting | Matplotlib |
| Config | python-dotenv |
| Production Server | Gunicorn |

---

## 🧠 Project Overview

AccessGuard solves the problem of single-factor authentication being too easy to compromise. A stolen PIN alone is not enough — the user must also present a matching face scan and voice sample.

**Authentication requires all four:**
1. Valid 7-digit User ID
2. Correct PIN
3. Face similarity ≥ 50%
4. Voice similarity ≥ 60%

---

## 🏗️ System Architecture

```
Browser (Webcam / Mic)
        │
        │  HTTP POST — base64 face + voice + PIN (up to 32 MB)
        ▼
  Flask App  (app.py)
        │
        ├── /store ──► decode base64 ──► AES-encrypt PIN
        │               └──► MongoDB (Binary face + Binary voice + encrypted PIN)
        │
        └── /recognize
                │
                ├── lookup user_id + decrypt PIN + verify  ──► MongoDB
                │
                ├── fetch Binary face bytes + Binary voice bytes from MongoDB
                │
                ├── face_recognition: 128-d descriptor distance (in-memory)
                ├── librosa: MFCC cosine similarity (in-memory, via BytesIO)
                │
                ├── PASS (both above threshold) ──► /welcome
                └── FAIL ──► recognize.html with error message

MongoDB: user_database.user_data
  {
    user_id:    "1234567",
    name:       "Rohan",
    rollno:     "21CS001",
    semester:   "6",
    pincode:    "<AES-EAX encrypted string>",
    face_data:  Binary(raw JPEG bytes),
    voice_data: Binary(raw WAV bytes)
  }

Disk (runtime only, git-ignored):
  plots/<user_id>.png   similarity score histogram
  plots/<user_id>.txt   raw score history (survives restarts)
  log/app.log           audit trail
```

---

## 📁 Folder Structure

```
AccessGuard/
│
├── app.py                          # Main application — all routes live here
│
├── utils/
│   ├── __init__.py
│   ├── encryption.py               # AES-EAX encrypt / decrypt helpers
│   ├── face_recognition.py         # Face encoding + similarity (in-memory bytes)
│   └── voice_recognition.py        # MFCC voice encoding + cosine similarity (in-memory)
│
├── templates/                      # Jinja2 HTML templates (server-rendered)
│   ├── base.html                   # Shared layout — navbar, footer, Bootstrap
│   ├── index.html                  # Home / landing page
│   ├── store.html                  # Registration form
│   ├── recognize.html              # Recognition / login form
│   └── welcome.html                # Post-auth success page (redirects after 10s)
│
├── static/
│   ├── css/styles.css              # Custom styles (supplements Bootstrap)
│   ├── js/scripts.js               # Shared client-side JS (webcam capture + voice)
│   └── pexels-pavel-danilyuk-6873897.jpg   # Background image
│
├── plots/                          # Runtime — similarity histograms + score history (git-ignored)
├── log/                            # Runtime — audit log (git-ignored)
│
├── shape_predictor_68_face_landmarks.dat       # dlib model (download separately)
├── dlib_face_recognition_resnet_model_v1.dat   # dlib model (download separately)
│
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
├── .gitignore
└── Procfile                        # Gunicorn entry point for deployment
```

---

## 🔐 Authentication Flow

### Registration (`/store`)
```
1. User fills form: name, rollno, semester, PIN
2. Browser captures face (webcam) → base64 JPEG
3. Browser captures voice (mic)   → base64 WAV
4. POST /store
5. Server decodes base64 → writes data/<user_id>.jpg + .wav
6. AES-EAX encrypts the file paths
7. MongoDB stores: { user_id, name, rollno, semester, pincode, encrypted_paths }
8. Redirect → /welcome
```

### Recognition (`/recognize`)
```
1. User enters user_id + PIN + captures face + voice
2. POST /recognize
3. MongoDB lookup by user_id → verify PIN
4. Decrypt face_data → file path → load stored JPEG
5. Decrypt voice_data → file path → load stored WAV
6. face_recognition: 128-d descriptor → distance → similarity = 1 - distance
7. librosa: MFCC (40 coefficients) → cosine similarity
8. face_sim >= 50% AND voice_sim >= 60% → redirect /welcome
9. Any failure → render recognize.html with specific error
```

### Encryption
- Algorithm: **AES-EAX** (authenticated encryption — confidentiality + integrity)
- Key: SHA-256 of `ENCRYPTION_SECRET` env var, truncated to 16 bytes
- What's encrypted: the **file path strings** in MongoDB (e.g. `data/1234567.jpg`)
- Raw biometric files live on disk; the DB never holds raw biometric data

---

## 🤖 Models & AI Clarification

### Is this an AI project?
Partially. The face recognition component uses a genuine pre-trained deep learning model. The voice component uses classical signal processing — no neural network involved.

### Face Recognition — dlib ResNet (deep learning)

| File | `dlib_face_recognition_resnet_model_v1.dat` |
|---|---|
| Type | Pre-trained deep neural network (ResNet) |
| Trained by | Davis King (dlib) on ~3 million face images |
| What it does | Converts any face image into a 128-dimensional embedding vector |
| Used by | `face_recognition` Python library, called in `utils/face_recognition.py` |
| Trained here? | No — weights are fixed, used only for inference |

Also requires `shape_predictor_68_face_landmarks.dat` — a pre-trained model that detects 68 facial landmark points (eyes, nose, jaw etc.) used to align the face before encoding.

**How matching works:** At registration, the face is encoded into a 128-number vector and stored in MongoDB. At login, the new face is encoded the same way and the Euclidean distance between the two vectors is computed. `similarity = 1 - distance`. If ≥ 50%, it passes.

### Voice Recognition — MFCC (signal processing, not AI)

| File | None — no model file |
|---|---|
| Type | Classical signal processing (Mel-Frequency Cepstral Coefficients) |
| Library | `librosa` |
| What it does | Extracts 40 MFCC coefficients that describe the tonal characteristics of a voice |
| Trained here? | N/A — no model, pure math |

**How matching works:** Both stored and new voice samples are converted to 40-number MFCC vectors. Cosine similarity between the two vectors is computed. If ≥ 60%, it passes.

### Summary

| Component | Technique | AI? |
|---|---|---|
| Face matching | dlib ResNet 128-d embeddings | Yes — pre-trained deep learning |
| Voice matching | MFCC + cosine similarity | No — signal processing |
| PIN verification | String comparison | No |

---

## ⚠️ Edge Cases & Error Handling

| Scenario | Handling |
|---|---|
| Face not detected | `get_face_encoding()` returns `None` → similarity = 0.0 → fails threshold |
| Corrupt voice file | `encode_voice()` catches exception → returns `None` → similarity = 0.0 |
| Wrong user ID | `find_one()` returns `None` → error rendered in template |
| Wrong PIN | String comparison fails → same error path |
| Face fails only | "Face does not match..." message |
| Voice fails only | "Voice does not match..." message |
| Both fail | Combined message with both percentages |
| Webcam unavailable | `cap.isOpened()` guard → returns `None` → `{success: false}` JSON |
| `data/` dir missing | Created at startup via `os.makedirs(..., exist_ok=True)` |

---

## 🚀 How to Run Locally

### Prerequisites
- Python 3.11+
- MongoDB running locally (or Atlas URI)
- Webcam + microphone

### 1. Clone
```bash
git clone https://github.com/your-username/accessguard.git
cd accessguard
```

### 2. Install dlib (Windows — pre-built wheel)
```bash
pip install https://github.com/z-mahmud22/Dlib_Windows_Python3.x/raw/main/dlib-19.24.1-cp311-cp311-win_amd64.whl
```
On Linux/macOS: `sudo apt install cmake && pip install dlib`

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
```

Open `.env` and fill in these three required values:

| Variable | How to get it |
|---|---|
| `FLASK_SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MONGO_URI` | `mongodb://localhost:27017/` for local, or your Atlas URI |
| `ENCRYPTION_SECRET` | `python -c "import secrets; print(secrets.token_hex(32))"` |

`MONGO_DB_NAME`, `FLASK_ENV`, `FLASK_DEBUG`, and `PORT` have sensible defaults and are optional for local development.

### 5. Run
```bash
python app.py
```
App runs at **http://localhost:5000**

---

## 🌐 Deployment

### Environment variables (production)

| Variable | Value |
|---|---|
| `FLASK_SECRET_KEY` | 64-char random hex (generate with `secrets.token_hex(32)`) |
| `FLASK_ENV` | `production` |
| `FLASK_DEBUG` | `0` |
| `MONGO_URI` | `mongodb+srv://<user>:<pass>@cluster.mongodb.net/` |
| `MONGO_DB_NAME` | `user_database` (or your preferred name) |
| `ENCRYPTION_SECRET` | 64-char random hex — **do not change after users are registered** |
| `PORT` | `8000` (or whatever your platform assigns) |

> ⚠️ `ENCRYPTION_SECRET` is used to derive the AES key. If you change it after users have registered, all existing encrypted file paths in MongoDB will fail to decrypt and those users will be locked out.

### Gunicorn
```bash
gunicorn app:app --bind 0.0.0.0:8000 --workers 2 --timeout 120
```

The `Procfile` is ready for Heroku / Railway.

> **Important:** `data/` must be persistent storage on the server. On ephemeral platforms (Heroku), use S3/GCS for biometric file storage.

---

## 🔮 Future Improvements

- Hash PINs with bcrypt (never store plaintext credentials)
- Liveness detection to prevent photo/recording spoofing
- Async biometric processing via Celery + Redis (unblock web workers)
- Store face/voice files in S3/GCS for horizontal scaling
- Rate limiting on `/recognize` (Flask-Limiter)
- WebRTC browser-side capture (removes webcam dependency on server)
- Structured JSON logging (structlog → Datadog/ELK)
- Unique DB index on `user_id` and `rollno`
