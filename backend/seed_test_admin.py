"""Seed a test admin user + a legacy opaque session token so backend tests can
authenticate as an admin without Supabase configured (dev/preview only)."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from config import db
import plans

TEST_ADMIN_EMAIL = "qa.admin@pikconnect.test"
TEST_ADMIN_USER_ID = "user_qa_admin_synology"


async def main():
    now = datetime.now(timezone.utc)
    user = {
        "user_id": TEST_ADMIN_USER_ID,
        "role": "admin",
        "name": "QA Admin",
        "email": TEST_ADMIN_EMAIL,
        "profile_complete": True,
        "uploads_disabled": False,
        "status": "active",
        "studio_profile": {"studio_name": "QA Studio", "contact_name": "QA Admin"},
        "auth_provider": "qa-seed",
        "created_at": now.isoformat(),
        "last_seen_at": now.isoformat(),
    }
    user.update(plans.new_studio_plan_fields())
    user["profile_complete"] = True
    await db.users.update_one(
        {"user_id": TEST_ADMIN_USER_ID},
        {"$set": user},
        upsert=True,
    )

    token = f"st_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    await db.user_sessions.insert_one({
        "session_token": token,
        "user_id": TEST_ADMIN_USER_ID,
        "created_at": now,
        "expires_at": now + timedelta(days=7),
    })

    print("TEST_ADMIN_USER_ID:", TEST_ADMIN_USER_ID)
    print("TEST_ADMIN_EMAIL:", TEST_ADMIN_EMAIL)
    print("TEST_ADMIN_BEARER_TOKEN:", token)


if __name__ == "__main__":
    asyncio.run(main())
