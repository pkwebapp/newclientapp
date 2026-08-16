"""Pluggable object-storage abstraction.

The rest of the app depends only on the `StorageBackend` interface, so the
bucket/endpoint can be swapped (Emergent-managed today, an S3-compatible bucket
later) by changing STORAGE_BACKEND in the environment and adding an impl below.
"""
import os
import io
import logging
import mimetypes

import requests

logger = logging.getLogger(__name__)

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"


class StorageBackend:
    """Interface every storage implementation must satisfy."""

    def init(self) -> None:
        raise NotImplementedError

    def put_object(self, path: str, data: bytes, content_type: str) -> dict:
        raise NotImplementedError

    def get_object(self, path: str) -> tuple[bytes, str]:
        raise NotImplementedError


class EmergentObjectStorage(StorageBackend):
    """Emergent-managed object storage (S3-compatible under the hood)."""

    def __init__(self, emergent_key: str):
        self._emergent_key = emergent_key
        self._storage_key = None

    def init(self) -> str:
        if self._storage_key:
            return self._storage_key
        resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": self._emergent_key}, timeout=30)
        resp.raise_for_status()
        self._storage_key = resp.json()["storage_key"]
        return self._storage_key

    def put_object(self, path: str, data: bytes, content_type: str) -> dict:
        key = self.init()
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
        if resp.status_code == 503:
            # stale storage_key -> reset and retry once
            self._storage_key = None
            key = self.init()
            resp = requests.put(
                f"{STORAGE_URL}/objects/{path}",
                headers={"X-Storage-Key": key, "Content-Type": content_type},
                data=data,
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json()

    def get_object(self, path: str) -> tuple[bytes, str]:
        key = self.init()
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
        if resp.status_code == 503:
            self._storage_key = None
            key = self.init()
            resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


_storage: StorageBackend | None = None


class CloudinaryStorage(StorageBackend):
    """Cloudinary-backed blob storage.

    Treats Cloudinary as an opaque key/value blob store keyed by ``path`` so it
    is a drop-in replacement for the Emergent object storage. Objects are stored
    as ``resource_type="raw"`` (exact bytes preserved, no re-encoding) with the
    storage ``path`` used verbatim as the ``public_id``. Delivery uses the
    version-less public URL which always resolves to the latest upload.
    """

    def __init__(self, cloud_name: str, api_key: str, api_secret: str):
        import cloudinary  # local import so the dep is only needed when used

        self._cloud_name = cloud_name
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )

    def init(self) -> str:
        return self._cloud_name

    def put_object(self, path: str, data: bytes, content_type: str) -> dict:
        import cloudinary.uploader

        return cloudinary.uploader.upload(
            io.BytesIO(data),
            resource_type="raw",
            public_id=path,
            overwrite=True,
            invalidate=True,
        )

    def get_object(self, path: str) -> tuple[bytes, str]:
        url = f"https://res.cloudinary.com/{self._cloud_name}/raw/upload/{path}"
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        return resp.content, ctype


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        from config import STORAGE_BACKEND, EMERGENT_LLM_KEY

        if STORAGE_BACKEND == "emergent":
            _storage = EmergentObjectStorage(EMERGENT_LLM_KEY)
        elif STORAGE_BACKEND == "cloudinary":
            cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
            api_key = os.environ.get("CLOUDINARY_API_KEY")
            api_secret = os.environ.get("CLOUDINARY_API_SECRET")
            if not (cloud_name and api_key and api_secret):
                raise RuntimeError(
                    "CLOUDINARY_CLOUD_NAME / CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET "
                    "are required for the cloudinary storage backend"
                )
            _storage = CloudinaryStorage(cloud_name, api_key, api_secret)
        else:
            raise RuntimeError(f"Unsupported STORAGE_BACKEND: {STORAGE_BACKEND}")
    return _storage
