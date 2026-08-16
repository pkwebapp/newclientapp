"""Pluggable face-recognition engine.

The app depends only on the `FaceEngine` interface. `MockFaceEngine` provides a
deterministic, no-cost implementation for development and demos. A
`RekognitionFaceEngine` can be dropped in (AWS Rekognition Collections) once AWS
credentials are configured, without touching any route code.

Selfie quality checks (brightness / blur / resolution) are performed with Pillow
+ numpy and are REAL — they run identically regardless of the active engine.
Side-profile (>45 deg) and face-out-of-frame checks require true face detection
and are therefore performed only by the Rekognition engine.
"""
import io
import os
import hashlib
import random
import logging

import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Quality thresholds (tuned to be lenient enough to avoid false rejects while
# still catching genuinely unusable selfies).
MIN_RESOLUTION = 120        # px, shortest side
DARK_THRESHOLD = 35         # mean luminance 0-255
GLARE_THRESHOLD = 240       # mean luminance 0-255
BLUR_THRESHOLD = 6.0        # variance of Laplacian


class QualityResult:
    def __init__(self, ok: bool, reason: str | None = None):
        self.ok = ok
        self.reason = reason

    def to_dict(self):
        return {"ok": self.ok, "reason": self.reason}


def _variance_of_laplacian(gray: np.ndarray) -> float:
    lap = (
        -4.0 * gray
        + np.roll(gray, 1, axis=0)
        + np.roll(gray, -1, axis=0)
        + np.roll(gray, 1, axis=1)
        + np.roll(gray, -1, axis=1)
    )
    return float(lap[1:-1, 1:-1].var())


def check_selfie_quality(image_bytes: bytes) -> QualityResult:
    """Real, engine-agnostic quality gate. Sunglasses/makeup/beard are NOT
    checked here — those are acceptable and must not block search."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        return QualityResult(False, "We couldn't read that photo. Please retake.")

    w, h = img.size
    if min(w, h) < MIN_RESOLUTION:
        return QualityResult(False, "Photo is too small. Move closer and retake.")

    gray = np.asarray(img.convert("L"), dtype=np.float64)
    brightness = float(gray.mean())
    if brightness < DARK_THRESHOLD:
        return QualityResult(False, "It's too dark. Find better lighting and retake.")
    if brightness > GLARE_THRESHOLD:
        return QualityResult(False, "Too much glare. Reduce lighting and retake.")

    if _variance_of_laplacian(gray) < BLUR_THRESHOLD:
        return QualityResult(False, "The photo looks blurry. Hold steady and retake.")

    return QualityResult(True)


class NotIndexedError(Exception):
    """Raised when searching a collection that doesn't exist yet in the engine."""


class FaceEngine:
    """Interface for face detection / indexing / search-by-image."""

    name = "base"

    def create_collection(self, event_id: str) -> str:
        raise NotImplementedError

    def ensure_collection(self, collection_id: str) -> str:
        """Create a collection with an explicit id if it doesn't exist (used by re-index)."""
        raise NotImplementedError

    def check_quality(self, image_bytes: bytes) -> "QualityResult":
        """Engine-specific selfie quality gate."""
        raise NotImplementedError

    def index_photo(self, collection_id: str, photo_id: str, image_bytes: bytes) -> list[dict]:
        """Detect + index all faces in a photo. Returns list of
        {face_id, bounding_box}."""
        raise NotImplementedError

    def search(self, collection_id: str, image_bytes: bytes, threshold: float,
               faces: list[dict], client_seed: str) -> list[dict]:
        """Search the collection for the person in image_bytes. Returns list of
        {face_id, photo_id, similarity} above `threshold`."""
        raise NotImplementedError

    def delete_faces(self, collection_id: str, face_ids: list[str]) -> None:
        raise NotImplementedError

    def delete_collection(self, collection_id: str) -> None:
        raise NotImplementedError


class MockFaceEngine(FaceEngine):
    """Deterministic stand-in. Faces-per-photo and per-client matches are derived
    from stable hashes so results are consistent across re-runs, giving a
    believable end-to-end experience with zero external cost."""

    name = "mock"

    def create_collection(self, event_id: str) -> str:
        return f"mock-collection-{event_id}"

    def ensure_collection(self, collection_id: str) -> str:
        return collection_id

    def check_quality(self, image_bytes: bytes) -> QualityResult:
        return check_selfie_quality(image_bytes)

    def index_photo(self, collection_id: str, photo_id: str, image_bytes: bytes) -> list[dict]:
        seed = int(hashlib.sha256(photo_id.encode()).hexdigest(), 16)
        rng = random.Random(seed)
        n = rng.randint(1, 4)  # 1-4 faces per photo
        faces = []
        for i in range(n):
            faces.append({
                "face_id": f"{photo_id}:{i}",
                "bounding_box": {
                    "Left": round(rng.uniform(0.05, 0.6), 3),
                    "Top": round(rng.uniform(0.05, 0.6), 3),
                    "Width": round(rng.uniform(0.1, 0.3), 3),
                    "Height": round(rng.uniform(0.1, 0.3), 3),
                },
            })
        return faces

    def search(self, collection_id: str, image_bytes: bytes, threshold: float,
               faces: list[dict], client_seed: str) -> list[dict]:
        if not faces:
            return []
        seed = int(hashlib.sha256(client_seed.encode()).hexdigest(), 16)
        rng = random.Random(seed)
        # Each client "matches" a deterministic ~20-40% subset of faces.
        match_fraction = rng.uniform(0.2, 0.4)
        matches = []
        for f in faces:
            fseed = int(hashlib.sha256((client_seed + f["face_id"]).encode()).hexdigest(), 16)
            frng = random.Random(fseed)
            if frng.random() < match_fraction:
                similarity = round(frng.uniform(threshold, 99.7), 2)
                matches.append({
                    "face_id": f["face_id"],
                    "photo_id": f["photo_id"],
                    "similarity": similarity,
                })
        matches.sort(key=lambda m: m["similarity"], reverse=True)
        return matches

    def delete_faces(self, collection_id: str, face_ids: list[str]) -> None:
        return None

    def delete_collection(self, collection_id: str) -> None:
        return None


import re as _re


def _sanitize_collection_id(raw: str) -> str:
    return _re.sub(r"[^A-Za-z0-9_.-]", "-", raw)[:255]


class RekognitionFaceEngine(FaceEngine):
    """Real AWS Rekognition Collections engine (one collection per event)."""

    name = "rekognition"

    def __init__(self, region: str, access_key: str, secret_key: str):
        import boto3

        self._client = boto3.client(
            "rekognition",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self.min_confidence = float(os.environ.get("FACE_MIN_DETECTION_CONFIDENCE", "90"))
        self.max_yaw = float(os.environ.get("FACE_MAX_ABS_YAW", "45"))
        self.max_pitch = float(os.environ.get("FACE_MAX_ABS_PITCH", "45"))

    def create_collection(self, event_id: str) -> str:
        cid = _sanitize_collection_id(f"lumiere-{event_id}")
        self.ensure_collection(cid)
        return cid

    def ensure_collection(self, collection_id: str) -> str:
        try:
            self._client.create_collection(CollectionId=collection_id)
        except self._client.exceptions.ResourceAlreadyExistsException:
            pass
        return collection_id

    def check_quality(self, image_bytes: bytes) -> QualityResult:
        # Cheap local resolution guard first (no API cost).
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img = ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            return QualityResult(False, "We couldn't read that photo. Please retake.")
        if min(img.size) < MIN_RESOLUTION:
            return QualityResult(False, "Photo is too small. Move closer and retake.")

        try:
            resp = self._client.detect_faces(Image={"Bytes": image_bytes}, Attributes=["DEFAULT"])
        except Exception:
            # If detection call fails, fall back to local checks rather than blocking.
            return check_selfie_quality(image_bytes)

        faces = resp.get("FaceDetails", [])
        if len(faces) == 0:
            return QualityResult(False, "No face detected. Center your face and retake.")
        if len(faces) > 1:
            return QualityResult(False, "Multiple faces detected — make sure only you are in frame.")
        f = faces[0]
        if f.get("Confidence", 0) < self.min_confidence:
            return QualityResult(False, "We couldn't confidently detect your face. Retake.")
        pose = f.get("Pose", {})
        if abs(pose.get("Yaw", 0)) > self.max_yaw:
            return QualityResult(False, "Turn to face the camera straight on and retake.")
        if abs(pose.get("Pitch", 0)) > self.max_pitch:
            return QualityResult(False, "Keep your head level and retake.")
        q = f.get("Quality", {})
        if q.get("Brightness", 100) < float(os.environ.get("FACE_MIN_BRIGHTNESS", "20")):
            return QualityResult(False, "It's too dark. Find better lighting and retake.")
        if q.get("Sharpness", 100) < float(os.environ.get("FACE_MIN_SHARPNESS", "8")):
            return QualityResult(False, "The photo looks blurry. Hold steady and retake.")
        b = f.get("BoundingBox", {})
        margin = 0.02
        if (
            b.get("Left", 0) < -margin
            or b.get("Top", 0) < -margin
            or b.get("Left", 0) + b.get("Width", 0) > 1 + margin
            or b.get("Top", 0) + b.get("Height", 0) > 1 + margin
        ):
            return QualityResult(False, "Your face is partly out of frame. Center yourself and retake.")
        return QualityResult(True)

    def index_photo(self, collection_id: str, photo_id: str, image_bytes: bytes) -> list[dict]:
        try:
            result = self._client.index_faces(
                CollectionId=collection_id,
                Image={"Bytes": image_bytes},
                ExternalImageId=photo_id,
                MaxFaces=100,
                QualityFilter="NONE",
                DetectionAttributes=["DEFAULT"],
            )
        except self._client.exceptions.ResourceNotFoundException:
            self.ensure_collection(collection_id)
            result = self._client.index_faces(
                CollectionId=collection_id,
                Image={"Bytes": image_bytes},
                ExternalImageId=photo_id,
                MaxFaces=100,
                QualityFilter="NONE",
                DetectionAttributes=["DEFAULT"],
            )
        except self._client.exceptions.InvalidImageFormatException:
            return []
        return [
            {"face_id": r["Face"]["FaceId"], "bounding_box": r["Face"].get("BoundingBox")}
            for r in result.get("FaceRecords", [])
        ]

    def search(self, collection_id, image_bytes, threshold, faces, client_seed) -> list[dict]:
        try:
            result = self._client.search_faces_by_image(
                CollectionId=collection_id,
                Image={"Bytes": image_bytes},
                FaceMatchThreshold=float(threshold),
                MaxFaces=4096,
                QualityFilter="NONE",
            )
        except self._client.exceptions.ResourceNotFoundException:
            raise NotIndexedError("This gallery hasn't been indexed yet. Ask the studio to re-index.")
        except self._client.exceptions.InvalidParameterException:
            # No searchable face in the selfie.
            return []
        matches = []
        for m in result.get("FaceMatches", []):
            face = m.get("Face", {})
            pid = face.get("ExternalImageId")
            if not pid:
                continue
            matches.append({
                "face_id": face.get("FaceId"),
                "photo_id": pid,
                "similarity": round(float(m.get("Similarity", 0)), 2),
            })
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches

    def delete_faces(self, collection_id: str, face_ids: list[str]) -> None:
        if not face_ids:
            return
        try:
            self._client.delete_faces(CollectionId=collection_id, FaceIds=face_ids)
        except Exception as e:
            logger.error(f"delete_faces failed: {e}")

    def delete_collection(self, collection_id: str) -> None:
        try:
            self._client.delete_collection(CollectionId=collection_id)
        except self._client.exceptions.ResourceNotFoundException:
            pass
        except Exception as e:
            logger.error(f"delete_collection failed: {e}")


_engine: FaceEngine | None = None


def get_face_engine() -> FaceEngine:
    global _engine
    if _engine is None:
        from config import FACE_ENGINE

        if FACE_ENGINE == "mock":
            _engine = MockFaceEngine()
        elif FACE_ENGINE == "rekognition":
            region = os.environ.get("AWS_REGION", "us-east-1")
            ak = os.environ.get("AWS_ACCESS_KEY_ID")
            sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
            if not ak or not sk:
                raise RuntimeError("AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY required for rekognition engine")
            _engine = RekognitionFaceEngine(region, ak, sk)
        else:
            raise RuntimeError(f"Unsupported FACE_ENGINE: {FACE_ENGINE}")
    return _engine
