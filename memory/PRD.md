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

## Iteration 2 (2026-06) — Rename + demo + S3 import
- Renamed app **Lumiere → PIK Connect** (app.json name, landing logo, boot splash, email from-name).
- Root-caused reported "no selfie step / no photos / no back button": client account had no shared
  gallery and dead-ended. Fixed by seeding a real demo gallery "Beach Wedding (Demo)" (6 AWS-indexed
  face photos) and granting it to the user's client account. The Scan-my-face step + back button appear
  once a gallery is shared.
- Verified admin login (admin@lumiere.studio / Admin@12345) works.
- Added **S3 import**: POST /api/events/{id}/import-s3 (bucket via S3_IMPORT_BUCKET=faceser, region auto)
  + admin "Import from S3" button — pulls images from the studio's own S3 bucket and indexes them.
- Relaxed /api/files auth so a granted client can load an event's COVER thumbnail without full access.
- Verified: 13/13 backend tests + full UI flows.

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
- [x] DONE (2026-06): Real AWS Rekognition engine live (FACE_ENGINE=rekognition, us-east-1).
      create/delete collection, IndexFaces (ExternalImageId=photo_id), SearchFacesByImage with
      configurable threshold, DetectFaces quality gate (no-face/multi-face/low-confidence/yaw>45°/
      pitch/out-of-frame/dark/blur), DeleteFaces. Verified: self-match 100%, cross-person no-match,
      quality rejections. Admin "Re-index faces" endpoint POST /events/{id}/reindex for migration.
- P1: SMS provider (e.g. Twilio) for real phone OTP delivery; set OTP_DEV_MODE=false in prod.
- P1: Bulk/zip photo upload for ~1000-photo events; background indexing queue + progress.
- P1: Also call DeleteFaces on Rekognition when admin deletes a client's face data (currently
      deletes the matched album + consent; the client's indexed event faces remain — acceptable
      since faces belong to event photos, not the selfie which is never stored).
- P2: Download/share My Photos; pinch-to-zoom viewer; watermarking; expiring share links.


## Album Flipbook Module (added)
- Separate product from the photo Gallery (own `albums` collection, routes `/api/albums/*`, self-contained WebGL viewer). Gallery untouched.
- Admin: Studio Console -> Albums (create, upload/replace PDF, publish/unpublish, copy link, preview, delete).
- Pipeline: admin uploads a designed album PDF (page1 front cover 12x18, interior 12x36 lay-flat spreads, last back cover) -> PyMuPDF renders each page to 3 JPEG resolutions -> stored in Cloudinary.
- Viewer: Three.js/WebGL flipbook served at `/api/albums/public/{token}/view`, embedded in Expo route `/a/{shareToken}` (iframe on web, WebView on native). Features: 3D cover opening, realistic page bending + dynamic shadows, continuous lay-flat spreads with center seam, drag/swipe/keyboard nav, zoom (wheel/pinch/double-tap), spread counter, optional page-turn sound, premium loader, WebGL fallback.
- Security: unguessable share_token; drafts require secret preview_token (?k=); published required for public access.
- Deps added: PyMuPDF (backend), react-native-webview + expo-document-picker (frontend).

## Session (June 2026): Album refinements — COMPLETE & TESTED (16/16 backend + full UI)
User request: no flash on page turns; landscape fullscreen on mobile; autoplay with speed option; fading exit button; Album Share/Access/Settings tabs like Gallery (link+QR, grants by email/phone visible in client app, music upload, archive, delete).
Implemented:
1. Viewer (backend/album_viewer.html): anti-flash (resolvedTex cache + best-cached-level instant fallback + leaf-face high-res preload + thumbs-first progressive load + paper-tone materials); forced-landscape CSS rotation on portrait touch devices with input remap (VW/VH/ptX/ptY); autoplay (default ON, 3.5s, Slow/Normal/Fast pill, pauses on interaction, stops at back cover); background music autoplay+mute btn; fading Exit(X) btn posting 'album-close' (RN WebView msg / iframe postMessage).
2. Native route app/a/[token].tsx: expo-screen-orientation LANDSCAPE lock on focus, unlock on exit; handles album-close from WebView and web iframe.
3. Backend album_routes.py: access grants (POST/GET/DELETE /albums/{id}/access, collection album_access_grants), GET /albums/client/mine (client app), music upload/delete (Cloudinary, own /music prefix, survives PDF replace since pages render under /pages prefix), archive/unarchive (public 403 when archived, preview key bypasses), PATCH autoplay/autoplay_interval (clamped 1.5-8s), delete also erases grants.
4. New admin screen app/admin/album/[id].tsx with Pages/Share/Access/Settings tabs; albums list cards now navigate to it; client home shows "Your Albums" section for granted albums.
Known non-blocking nits: OTP demo-code banner can overlay "Your Albums" header on small screens; pre-existing RN-web shadow*/pointerEvents deprecation warnings.

## Feature: Google Drive Galleries (added)
- Admin creates a gallery by pasting a PUBLIC Google Drive folder link ("Anyone with the link → Viewer"). No API key required (reads Google's embeddedfolderview); GOOGLE_DRIVE_API_KEY optional for richer metadata.
- Originals stay on Drive. App stores only metadata + serves web-sized previews via proxy GET /api/gdrive/thumb/{fileId}?w=. Face search (AWS Rekognition) runs on previews, mapped by Drive file id.
- Endpoints: POST /api/events/gdrive, POST /api/events/{id}/sync (add/update/remove counts, idempotent). Events carry source="gdrive". Recurses subfolders and preserves folder_path.
- Frontend: New Event screen source toggle (Upload / Google Drive) + link field; admin gallery shows "Sync now" panel; dashboard shows a "Drive" badge. Client masonry grid, face-scan, likes/proofing all reuse existing flows.



## Cloud integration configuration (2026-08)
- [x] User-provided Cloudinary credentials configured in backend-only environment.
- [x] User-provided AWS credentials configured for Rekognition in `ap-southeast-2`; S3 import bucket set to `faceser`.
- Pending: live integration smoke test and optional frontend browser test.



## Import session (2026-08)
- [x] Confirmed workspace origin is `https://github.com/pkwebapp/newclientapp`.
- [x] Restored missing local runtime dependencies and environment files without changing application code.
- [x] Restarted backend and Expo services; backend health endpoint and frontend preview respond successfully.
- Note: local clone does not contain the prior Cloudinary/AWS secrets; current runtime defaults to mock face engine and Emergent storage until credentials are intentionally configured.



## Feature: CRM client-group access assignments (2026-08)
- Added multi-client assignments for galleries and flipbook albums from each Admin Access tab.
- Assignment resolves through each Client/Family's contact email/phone, so current and future contacts inherit access without manual grants.
- Gallery assignments support Full gallery vs Matched only; album assignments match direct album access. Removing an assignment removes only the automatic group access.

- Assignment relationship is many-to-many: one client can be assigned to multiple galleries/albums, and each gallery/album can include multiple clients.



## Feature: Client full-screen photo zoom (2026-08)
- Added pinch zoom from 1x to 4x plus double-tap zoom/reset in the client gallery full-screen viewer.
- Existing photo paging, close, like, download, captions, and match-score behavior remain available.



## Feature: Searchable client access groups (2026-08)
- Access tabs query CRM clients only after an explicit search, keeping the UI usable for large client directories while preserving assigned groups.
- Direct shared-access rows show the matching Client/Family name and contact name when the grant matches a CRM contact, with email/phone fallback.



## Feature: Client full-screen image sharing (2026-08)
- Added a Share action that shares image bytes through the native system share sheet instead of a PIK Connect link.
- Images over 2 MB are recompressed to JPEG before sharing; web uses Web Share API when available and downloads a compressed fallback otherwise.
- Added SDK 54-compatible `expo-sharing`, `expo-file-system`, and `expo-image-manipulator` dependencies.



## Feature: Web landing page screen separation (2026-08)
- Desktop web hero now fills one viewport so the How it works section begins on the next scroll screen.
- Mobile and native hero sizing remain unchanged.



## Refinement: Service-specific enquiry messages (2026-08)


## Feature: Offline client gallery previews (2026-08)
- Client gallery previews are persisted in the native app document directory or browser Cache API, with metadata in AsyncStorage.
- Full-access galleries continue fetching and caching all pages in the background; offline open restores cached photos.
- Offline likes queue locally and sync after the next successful online refresh. Face scanning shows an offline limitation because Rekognition is cloud-based.

- Service cards now open WhatsApp with a pre-filled message naming the selected service.


## Feature: Client gallery fetch progress (2026-08)
- Client gallery opening now shows a live `fetched photos / total photos` counter with a progress bar while remaining pages load and cache.
- Offline restored galleries show the cached photo count and offline status.


## Refinement: Branded web favicon (2026-08)
- Added a compact orange PIK Connect aperture favicon as an inline base64 SVG.
- Retained the existing PNG alternate favicon and Apple touch icon for compatibility.



## Feature: Super Admin Dashboard V1 (2026-08)
- Added protected Super Admin login and a responsive dashboard for platform statistics, photographers, memberships, galleries, storage, activity logs, and basic settings.


## Refinement: 30-second gallery preload fallback (2026-08)
- Client galleries wait up to 30 seconds while the animated loader shows fetched/total progress, then open with available photos and continue fetching in the background.
- The progress card remains visible after opening until remaining pages are loaded; users can interact with already fetched photos immediately.

- Photographer controls include upload disable/enable and suspend/restore with confirmation; disabling uploads preserves existing galleries and images.
- V1 uses live platform counts plus simple plan metadata; complex billing, RBAC, and advanced analytics are intentionally deferred.


## Refinement: Footer social destinations (2026-08)
- Updated Instagram, YouTube, Facebook, LinkedIn, and X footer links to the user's supplied profiles.
- WhatsApp and email footer actions remain unchanged.




## Feature: Luxe loading animation (2026-08)
- Added an animated aperture/ring loader inspired by the supplied PIK Connect visual.
- It appears during auth bootstrap and full client-gallery preloading, with optional fetched/total progress.



## Refinement: Complete gallery preloading (2026-08)
- Full-access client galleries now fetch and cache every accessible photo preview before rendering the grid, with a live fetched/total counter during loading.
- If a later page fails, already fetched photos remain available and pagination can retry the remainder.


- Design Services now includes website design; the general WhatsApp CTA remains generic.



## Bug fix: Reliable back-button navigation (2026-08)
- Added a shared `goBackOr` helper that uses history when available and explicit route fallbacks for direct links, refreshes, bookmarks, and native cold starts.
- Applied to login, admin, client, gallery, album, settings, create, selfie, booking, and review screens.



## Configuration: Cloudinary + AWS Rekognition verified (2026-08)
- [x] Backend runtime now uses `STORAGE_BACKEND=cloudinary` with the supplied Cloudinary account.
- [x] Backend runtime now uses `FACE_ENGINE=rekognition` in `ap-southeast-2`; S3 import bucket `faceser` configured.
- [x] Verified health, admin auth, Cloudinary upload/CDN serving/delete, Rekognition indexing lifecycle, S3 import, and cleanup with a throwaway event.
- Secrets remain backend-only in local runtime environment files and were not added to frontend code or committed source.



## Bug fix: Super Admin password rejected (2026-08)
- Root cause: repository bootstrap recreated `backend/.env` without `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD`, so the idempotent seed did not create the platform-owner account.
- Added the backend-only Super Admin credentials, restarted the API, and verified login, overview access, wrong-password rejection, and normal-admin role isolation.

## Gallery Mismatch Hardening (June 2026 fork)
- PhotoGrid.tsx hardened against photo identity mismatch:
  - `recyclingKey={photoId}` added to expo-image in BrandedImage (official anti-recycling-staleness prop)
  - Thumbnail cachePolicy reduced from "memory-disk" to "memory" (fullscreen already "none")
  - BrandedImage state now resets synchronously during render (not useEffect) — no stale frame on recycled cells
  - FullscreenViewer FlatList: initialNumToRender=1, windowSize=3, removeClippedSubviews=false


## Universal Calendar Date Picker (June 2026 fork)
- Extracted the working calendar UI from `admin/new-event.tsx` into a reusable component
  `/app/frontend/src/components/DatePickerField.tsx` (exports `DatePickerField`, `todayIso`,
  `toIsoDate`, `formatDateLabel`).
- Replaced ALL remaining `TextField` date inputs with the calendar picker, defaulting to today:
  - `app/client/book.tsx` — Preferred date (initial value = today)
  - `app/admin/new-client.tsx` — Important Dates rows (new rows initialised to today)
  - `app/admin/client/[id].tsx` — DateModal for adding/editing important dates
- Data contract unchanged: still stores ISO `YYYY-MM-DD` strings; back-end untouched.
- Behaviour: taps open a full-screen glass modal with month navigation, "Jump to today"
  shortcut, tap-a-day to select. Weekly grid with proper padding.


## 10s Gallery Early-Open + Background Load (June 2026 fork)
- Client gallery (`app/client/event/[id].tsx`): reduced PRELOAD_TIMEOUT_MS 30s → 10s.
  After 10s the gallery opens and the remaining photos keep paginating in the background
  (progress bar shows "Gallery open · loading remaining"). Scroll triggers loadMoreAll.
- Public share-link gallery (`app/g/[id].tsx`): added 10s early-open. Full-screen spinner
  now only blocks for up to 10s; after that the header + an inline "Loading photos…" loader
  appear while the first batch finishes. Once photos exist, PhotoGrid shows a bottom
  "loading more…" indicator and scroll drives pagination (onEndReached → loadMoreAll).


## Cache Warm-Up + Scroll Prefetch (June 2026 fork)
- Scroll Prefetch: PhotoGrid FlashList onEndReachedThreshold 0.6 → 1.2, so the next
  batch starts loading ~1 screen earlier (smoother infinite scroll in both galleries).
- Cache Warm-Up (client gallery `app/client/event/[id].tsx`): added `warmStart()` that
  paints the last cached gallery instantly (from offline-gallery cache) while the fresh
  network load runs in the background. When warmed, the 10s early-release timer is skipped
  and mid-flight allPhotos updates are suppressed so cached photos never "shrink"; the fresh
  full set replaces them only when the background load completes.
- Cache Warm-Up (public gallery `app/g/[id].tsx`): added lightweight per-tab cache via new
  `cachePublicTab`/`restorePublicTab` helpers in offline-gallery.ts. On tab load the last
  cached photos show instantly (grid + bottom "loading more…" refresh indicator), then fresh
  data replaces + re-caches. Bounded to 120 photos per tab.


## Studio Profile Onboarding Gate (June 2026 fork)
- Studios must complete a profile before reaching the /admin dashboard (create galleries).
- Backend (server.py): new `StudioProfile` model + `POST /api/auth/admin/profile` (auth,
  role=admin). Saves studio_profile{contact_name, studio_name, phone, purpose, city, country,
  website?, team_size?, galleries_per_month?, referral_source?}, sets profile_complete=true,
  and syncs user.name→studio_name, user.phone→phone. `_public_user` now returns
  profile_complete + studio_profile. Blank required field → 400; missing key → 422; no auth → 401.
- Frontend: `/app/frontend/app/studio-onboarding.tsx` (top-level, no admin shell). Gate added in
  `admin/_layout.tsx`: incomplete admins → Redirect to /studio-onboarding. AuthContext User type
  extended with profile_complete + studio_profile; onboarding calls refresh() then replace('/admin').
- Required: name, studio name, phone(>=6), purpose(chips), city, country. Optional: website/IG,
  team size, galleries/month, referral. Applies to ALL incomplete studios (existing too).
  Superadmin + client accounts unaffected.
- Verified: backend 8/8 pytest (tests/test_studio_onboarding.py) + frontend e2e via testing agent.
