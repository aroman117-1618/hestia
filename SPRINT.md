# Current Sprint: Wire Frontend to Backend

**Started:** 2026-02-28
**Target:** 3 sequential sprints (~7 sessions)
**Plan:** `.claude/plans/nifty-exploring-rain.md`
**Audit:** `docs/plans/wire-frontend-backend-audit-2026-02-28.md`

## Sprint 1: DevOps & Deployment

### 1A. Backend Invite Endpoints
- **Phase:** Done
- **Key files:** `hestia/api/routes/auth.py` (invite, register-with-invite, re-invite), `hestia/api/middleware/auth.py` (invite tokens), `hestia/api/schemas.py` (invite models)
- **Notes:** 4 new endpoints, nonce-based one-time invites, rate limiting (5/hour), recovery via re-invite. 28 tests passing.

### 1B. iOS/macOS Onboarding Flow
- **Phase:** Done
- **Key files:** `HestiaApp/Shared/Views/Auth/OnboardingView.swift`, `QRScannerView.swift`, `PermissionsOnboardingView.swift`, `HestiaApp/macOS/Views/Auth/MacOnboardingView.swift`
- **Notes:** iOS: QR scanner + multi-step flow. macOS: paste JSON payload. Both build clean with Swift 6 strict concurrency. HestiaShared SPM updated with invite models + `registerWithInvite()`.

### 1C. Permissions Harmony
- **Phase:** Done
- **Key files:** `HestiaApp/Shared/Views/Auth/PermissionsOnboardingView.swift`, `HestiaApp/Shared/App/ContentView.swift`
- **Notes:** Apple HIG-compliant guided flow: Calendar → Reminders → Health → Notifications → Biometric. One at a time, Skip option, grant summary. Integrated between auth and main app in ContentView.

### 1D. Tests
- **Phase:** Done
- **Key files:** `tests/test_auth_invite.py`
- **Notes:** 28 tests for invite generation, expiry, nonce consumption, register-with-invite, re-invite, rate limiting, device listing. All passing.

## Sprint 2: Explorer — Both Platforms (~3 sessions)

### 2A. Backend Explorer Module
- **Phase:** Research
- **Key files:** TBD — `hestia/explorer/` (new module)
- **Notes:** Manager pattern: models.py + database.py + manager.py. Aggregates mail + notes + reminders + files + drafts via asyncio.gather(). TTL cache layer.

### 2B. Backend Explorer API
- **Phase:** Research
- **Key files:** TBD — `hestia/api/routes/explorer.py`
- **Notes:** 6 endpoints: resource list/detail/content, draft CRUD.

### 2C. iOS Explorer View
- **Phase:** Research
- **Key files:** TBD — `HestiaApp/Shared/Views/Explorer/`, `HestiaApp/Shared/ViewModels/ExplorerViewModel.swift`
- **Notes:** Section filter chips + search + resource list. New tab in ContentView.

### 2D. macOS Explorer Enhancement
- **Phase:** Research (half-time cut candidate)
- **Notes:** Add API-backed resource loading alongside existing local file browser.

### 2E. APIClient Extensions
- **Phase:** Research
- **Notes:** `APIClient+Explorer.swift` with 5 methods.

### 2F. Tests
- **Phase:** Research

## Sprint 3: Command Center / Newsfeed (~2 sessions)

### 3A. Backend Newsfeed
- **Phase:** Not started
- **Notes:** NewsfeedItem types: alert, insight, news, order, event, task. RSS via feedparser + APScheduler.

### 3B. Backend Newsfeed API
- **Phase:** Not started

### 3C. iOS Command Center Rewrite
- **Phase:** Not started
- **Notes:** BriefingCard + FilterBar + NewsfeedTimeline replacing current tab layout.

### 3D. macOS Command View Update
- **Phase:** Not started

### 3E-F. APIClient + Tests
- **Phase:** Not started

---

## Previous Sprint: Claude Code Config Refresh (COMPLETE)

All topics done: Direct API config, Figma MCP, macOS app (Hestia), Skills redesign, Cheat sheet.
Deferred: CI/CD pipeline, Fireproof (server reliability).
