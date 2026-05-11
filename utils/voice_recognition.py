import base64
import io
import logging

import numpy as np
import librosa
from scipy.spatial.distance import cosine

logger = logging.getLogger(__name__)


def capture_voice_data() -> str | None:
    """
    Record a voice sample from the microphone.
    Returns a base64-encoded WAV string, or None on failure.
    """
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
        return base64.b64encode(audio.get_wav_data()).decode()
    except Exception as exc:
        logger.warning("Voice capture failed: %s", exc)
        return None


def _encode_voice_bytes(wav_bytes: bytes) -> np.ndarray | None:
    """Extract 40 MFCC coefficients from raw WAV bytes."""
    try:
        buf = io.BytesIO(wav_bytes)
        y, sr = librosa.load(buf, sr=None)
        if len(y) == 0:
            logger.warning("Voice encoding: empty audio signal")
            return None
        return np.mean(librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40).T, axis=0)
    except librosa.util.exceptions.ParameterError as exc:
        logger.warning("Voice encoding parameter error: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Voice encoding failed: %s", exc)
        return None


def calculate_voice_similarity(stored_voice_bytes: bytes, new_voice_b64: str) -> float:
    """
    Compare stored voice bytes (from MongoDB) against a base64-encoded new sample.
    Returns cosine similarity in [0, 1].
    """
    try:
        new_bytes = base64.b64decode(new_voice_b64)
    except Exception as exc:
        logger.warning("Voice b64 decode failed: %s", exc)
        return 0.0

    stored = _encode_voice_bytes(stored_voice_bytes)
    new    = _encode_voice_bytes(new_bytes)

    if stored is not None and new is not None:
        return float(max(0.0, 1.0 - cosine(stored, new)))
    return 0.0
