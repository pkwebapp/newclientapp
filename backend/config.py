"""Shared configuration, database client, and environment access."""
import os
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# --- Mongo (protected env, never modify URL) ---
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# --- App config ---
APP_NAME = "lumiere-gallery"
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
DEFAULT_SIMILARITY_THRESHOLD = float(os.environ.get("DEFAULT_SIMILARITY_THRESHOLD", "85"))
FACE_ENGINE = os.environ.get("FACE_ENGINE", "mock")
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "emergent")
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "mock")
# Preview convenience: return OTP codes in API responses so flows are testable
# without inbox/SMS access. MUST be "false" in production.
OTP_DEV_MODE = os.environ.get("OTP_DEV_MODE", "true").lower() == "true"

ADMIN_SEED_EMAIL = os.environ.get("ADMIN_SEED_EMAIL", "admin@lumiere.studio")
ADMIN_SEED_PASSWORD = os.environ.get("ADMIN_SEED_PASSWORD", "Admin@12345")

# Public base URL used to build shareable gallery links / QR codes.
PUBLIC_BASE_URL = (
    os.environ.get("PUBLIC_BASE_URL")
    or os.environ.get("APP_URL")
    or ""
).rstrip("/")
