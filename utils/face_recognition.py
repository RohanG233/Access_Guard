import base64
import logging

import cv2
import numpy as np
import face_recognition

logger = logging.getLogger(__name__)


def get_face_encoding(image_rgb: np.ndarray) -> np.ndarray | None:
    """Return the 128-d face encoding for the first face found in an RGB image."""
    try:
        # dlib on Windows requires a writeable, C-contiguous uint8 RGB array
        image_rgb = np.array(image_rgb, dtype=np.uint8, order='C')
        encodings = face_recognition.face_encodings(image_rgb)
        if not encodings:
            logger.debug("No face detected in image")
        return encodings[0] if encodings else None
    except RuntimeError as exc:
        logger.warning("Face encoding runtime error: %s", exc)
        return None


def _b64_to_rgb(b64_string: str) -> np.ndarray | None:
    """Decode a base64 JPEG/PNG string to an RGB numpy array."""
    try:
        img_bytes = np.frombuffer(base64.b64decode(b64_string), np.uint8)
        bgr = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
        if bgr is None:
            logger.warning("cv2 could not decode base64 image")
            return None
        return np.array(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), dtype=np.uint8, order='C')
    except Exception as exc:
        logger.warning("Face b64 decode failed: %s", exc)
        return None


def _bytes_to_rgb(raw_bytes: bytes) -> np.ndarray | None:
    """Decode raw image bytes to an RGB numpy array."""
    try:
        arr = np.frombuffer(raw_bytes, np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if bgr is None:
            logger.warning("cv2 could not decode stored face bytes")
            return None
        return np.array(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), dtype=np.uint8, order='C')
    except Exception as exc:
        logger.warning("Face bytes decode failed: %s", exc)
        return None


def calculate_similarity(stored_face_bytes: bytes, new_face_b64: str) -> float:
    """
    Compare stored face bytes (from MongoDB) against a base64-encoded new face.
    Returns a similarity score in [0, 1].
    """
    stored_rgb = _bytes_to_rgb(stored_face_bytes)
    new_rgb    = _b64_to_rgb(new_face_b64)

    if stored_rgb is None:
        logger.warning("calculate_similarity: could not decode stored face bytes (len=%d)", len(stored_face_bytes))
        return 0.0
    if new_rgb is None:
        logger.warning("calculate_similarity: could not decode new face b64")
        return 0.0

    logger.debug("stored_rgb shape=%s dtype=%s", stored_rgb.shape, stored_rgb.dtype)
    logger.debug("new_rgb    shape=%s dtype=%s", new_rgb.shape,    new_rgb.dtype)

    stored_enc = get_face_encoding(stored_rgb)
    new_enc    = get_face_encoding(new_rgb)

    if stored_enc is None:
        logger.warning("calculate_similarity: no face detected in STORED image")
        return 0.0
    if new_enc is None:
        logger.warning("calculate_similarity: no face detected in NEW image")
        return 0.0

    distance = face_recognition.face_distance([stored_enc], new_enc)[0]
    score = float(max(0.0, 1.0 - distance))
    logger.debug("face distance=%.4f score=%.4f", distance, score)
    return score
