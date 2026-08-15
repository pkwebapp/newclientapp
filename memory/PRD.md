# Lumiere Gallery — PRD & Build Log

## Original Problem Statement
Full-stack client photo gallery app (Expo web + mobile, FastAPI, MongoDB) for a photography
business (weddings, events, studio, school, nightlife, corporate). Core feature: clients take a
selfie and the app finds their photos in an event gallery using face recognition. Photos in
cloud object storage (configurable/S3-like). Face recognition via AWS Rekognition Collections
(one per event) — detection, indexing, search-by-image, quality checks on selfies. Ranked
matches above configurable similarity threshold (default ~85%). Auto private "My Photos" album
per client. Strict access control (no public browsing; email/phone OTP for clients;
admin-managed gallery access; full-gallery access optional). Biometric consent before selfie
processing; admin can delete client face data.

## User Choices (gathered)
- Face recognition: pluggable engine, **MockFaceEngine now**, AWS Rekognition interface ready.
- Photo storage: **Emergent-managed Object Storage** (behind a StorageBackend abstraction).
- Client verification: **Email OTP + Phone OTP**.
- Admin login: **email+password (seeded) AND Google** (Emergent-managed OAuth).
- Design: **Clean & premium** → "Glass/Luxe" dark theme, gold accent, serif display.

## Architecture
- Backend: FastAPI (`/api` prefix), MongoDB (motor). String UUID ids, `_id` projected out.
  - Modules: `config.py`, `storage_service.py` (pluggable), `face_engine.py` (pluggable +
    Pillow/numpy quality checks), `email_service.py` (Resend + guardrail gate), `auth_utils.py`
    (bcrypt + opaque session tokens), `server.py` (routes).
- Frontend: Expo Router (stack), expo-image, expo-blur, expo-linear-gradient, expo-camera,
  expo-image-picker, react-native-keyboard-controller. AuthContext + Toast providers.
- Integrations: Emergent Object Storage, Emergent Resend email, Emergent Google OAuth.

## Data Model
users, user_sessions (TTL), otp_codes, events, photos, faces (face↔photo), access_grants,
client_albums (My Photos), consent_logs.

## Selfie → Match Flow
consent gate → capture/upload → real quality checks (brightness/blur/resolution, retake prompt)
→ engine.search → dedupe by photo (multi-face once) → filter ≥ threshold → upsert private
My Photos album. Raw selfie never stored (only match references).

## Implemented (2026-06)
- [x] Admin auth: email+password (seeded admin), register, Google OAuth session exchange.
- [x] Client auth: email + phone OTP (dev_code in OTP_DEV_MODE; real email via Resend).
- [x] Events CRUD, per-event similarity threshold (50–100), categories.
- [x] Photo upload → thumbnail + original to object storage → mock face indexing → status.
- [x] Access grants (email/phone), full-gallery toggle, revoke.
- [x] Client shared-events list, gallery with My Photos / All Photos (glass segmented).
- [x] Consent screen + selfie camera (front) with silhouette mask + library upload fallback.
- [x] Selfie search, ranked matches, auto My Photos album, re-scan.
- [x] Token-authenticated image serving (bearer + ?token= for web).
- [x] Admin: indexing status, client face-data deletion (right-to-be-forgotten).
- [x] Tested: 37/37 backend pytest, frontend flows verified.

## Credentials
- Admin: admin@lumiere.studio / Admin@12345 (see /app/memory/test_credentials.md)

## Backlog / Remaining
- P0: Swap MockFaceEngine → RekognitionFaceEngine when AWS keys provided (create collection,
  index_faces, search_faces_by_image, quality via Rekognition attributes incl. pose >45° &
  face-out-of-frame). FACE_ENGINE=rekognition.
- P1: SMS provider (e.g. Twilio) for real phone OTP delivery; set OTP_DEV_MODE=false in prod.
- P1: Bulk/zip photo upload for ~1000-photo events; background indexing queue + progress.
- P2: Download/share My Photos; pinch-to-zoom in fullscreen viewer; watermarking; expiring
  share links; per-event storage cleanup on deletion.
