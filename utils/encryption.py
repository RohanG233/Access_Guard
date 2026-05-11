import os
import base64
import hashlib
from Crypto.Cipher import AES

# Key is derived once at import time from the environment variable.
# load_dotenv() is called in app.py before any import, so os.environ is ready.
_raw = os.environ.get('ENCRYPTION_SECRET', 'my_secret_key_change_me')
SECRET_KEY = hashlib.sha256(_raw.encode()).digest()[:16]  # 16-byte AES key


def encrypt_data(data: str) -> str:
    """AES-EAX encrypt a string → base64 ciphertext."""
    cipher = AES.new(SECRET_KEY, AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(data.encode())
    return base64.b64encode(cipher.nonce + tag + ciphertext).decode()


def decrypt_data(token: str) -> str:
    """Decrypt a base64 AES-EAX token → original string."""
    raw = base64.b64decode(token)
    cipher = AES.new(SECRET_KEY, AES.MODE_EAX, nonce=raw[:16])
    return cipher.decrypt_and_verify(raw[32:], raw[16:32]).decode()
