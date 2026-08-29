"""Emergent-managed push notifications (SuprSend relay).

The backend is the only party that talks to the Emergent push service. The
frontend registers device tokens via ``POST /api/register-push`` and the app
sends notifications on server-side events through :func:`push_user` /
:func:`send_push`. All sends are best-effort — a push failure must never block
the primary operation.
"""
import os
import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

PUSH_BASE_URL = "https://integrations.emergentagent.com"
# Placeholder locally; the deployment pipeline injects the real key at build time.
PUSH_KEY = os.environ.get("EMERGENT_PUSH_KEY", "placeholder")

_client = httpx.AsyncClient(
    base_url=PUSH_BASE_URL,
    headers={"X-Push-Key": PUSH_KEY},
    timeout=10.0,
)

push_router = APIRouter(prefix="/api")


class RegisterPushBody(BaseModel):
    user_id: str
    platform: str  # "android" | "ios"
    device_token: str


@push_router.post("/register-push", status_code=201)
async def register_push(body: RegisterPushBody):
    resp = await _client.post("/api/v1/push/users/register", json=body.model_dump())
    if resp.status_code == 401:
        raise HTTPException(500, "EMERGENT_PUSH_KEY missing or invalid")
    if resp.status_code >= 500:
        raise HTTPException(502, "Push provider unavailable")
    resp.raise_for_status()
    return {"status": "registered"}


async def send_push(recipients: list[str], data: dict, idempotency_key: str | None = None) -> None:
    """Relay a push to the given user IDs. Raises on upstream failure — most
    callers should use :func:`push_user`, which swallows errors."""
    recipients = [r for r in recipients if r]
    if not recipients:
        return
    if len(recipients) > 100:
        raise ValueError("max 100 recipients per /trigger call; chunk before sending")
    if "title" not in data or "message" not in data:
        raise ValueError("data must include title and message")
    payload: dict = {"recipients": recipients, "data": data}
    if idempotency_key:
        payload["$idempotency_key"] = idempotency_key
    resp = await _client.post("/api/v1/push/trigger", json=payload)
    if resp.status_code == 401:
        raise HTTPException(500, "EMERGENT_PUSH_KEY missing or invalid")
    if resp.status_code >= 500:
        raise HTTPException(502, "Push provider unavailable")
    resp.raise_for_status()


async def push_user(user_id: str | None, title: str, message: str, action_url: str | None = None) -> None:
    """Fire-and-forget push to a single user. Never raises."""
    if not user_id:
        return
    data: dict = {"title": title, "message": message}
    if action_url:
        data["action_url"] = action_url
    try:
        await send_push([user_id], data)
    except Exception as e:  # noqa: BLE001 — push must never block the caller
        logger.warning(f"Push failed (non-blocking) for {user_id}: {e}")
