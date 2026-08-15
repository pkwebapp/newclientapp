"""Pluggable object-storage abstraction.

The rest of the app depends only on the `StorageBackend` interface, so the
bucket/endpoint can be swapped (Emergent-managed today, an S3-compatible bucket
later) by changing STORAGE_BACKEND in the environment and adding an impl below.
"""
import os
import logging
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


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        from config import STORAGE_BACKEND, EMERGENT_LLM_KEY

        if STORAGE_BACKEND == "emergent":
            _storage = EmergentObjectStorage(EMERGENT_LLM_KEY)
        else:
            raise RuntimeError(f"Unsupported STORAGE_BACKEND: {STORAGE_BACKEND}")
    return _storage
