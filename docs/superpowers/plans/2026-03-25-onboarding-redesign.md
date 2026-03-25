# Onboarding Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace broken iOS onboarding (unreadable Lottie, dead-end QR flow) with premium dark atmospheric design, Sign in with Apple auth, and smart server URL discovery.

**Architecture:** SwiftUI Canvas-based animated orb (reusable `HestiaOrbView` with state machine), new `POST /v1/auth/register-with-apple` backend endpoint validating Apple identity tokens, simplified two-path registration (Apple Sign In → smart URL pre-fill, QR as escape hatch). Visual: dark-to-teal atmospheric gradient, Liquid Glass pill button.

**Tech Stack:** SwiftUI (Canvas + TimelineView), AuthenticationServices (Sign in with Apple), python-jose (Apple JWT validation, already installed), FastAPI, SQLite migration.

**Spec:** `docs/superpowers/specs/2026-03-25-onboarding-redesign-design.md`
**Second opinion:** `docs/plans/onboarding-redesign-second-opinion-2026-03-25.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `hestia/api/schemas/auth.py` | Modify | Add `AppleRegisterRequest`, `AppleRegisterResponse` |
| `hestia/api/routes/auth.py` | Modify | Add `POST /v1/auth/register-with-apple` endpoint |
| `hestia/api/invite_store.py` | Modify | Add `apple_user_id` column migration + lookup methods |
| `tests/test_auth_apple.py` | Create | Backend tests for Apple auth endpoint |
| `HestiaApp/Shared/Views/Common/HestiaOrbView.swift` | Create | SwiftUI Canvas animated orb with state machine |
| `HestiaApp/Shared/Views/Common/OnboardingBackground.swift` | Create | Dark-to-teal atmospheric gradient |
| `HestiaApp/Shared/Views/Auth/OnboardingView.swift` | Replace | Redesigned onboarding with new visual + auth flow |
| `HestiaApp/Shared/ViewModels/OnboardingViewModel.swift` | Replace | New state machine (welcome → appleSignIn → serverURL → connecting → success) |
| `HestiaShared/Sources/HestiaShared/Auth/AuthService.swift` | Modify | Add `registerWithApple(identityToken:)` method |
| `HestiaShared/Sources/HestiaShared/Networking/APIClient.swift` | Modify | Add `registerWithApple()` API call |
| `HestiaApp/Shared/App/ContentView.swift` | Modify | Update RootView transition for new onboarding states |
| `HestiaApp/iOS/HestiaApp.entitlements` | Modify | Add Sign in with Apple entitlement |
| `HestiaApp/project.yml` | Modify | Add AuthenticationServices framework |

---

## Task 1: Backend — Apple Auth Schemas

**Files:**
- Modify: `hestia/api/schemas/auth.py`

- [ ] **Step 1: Add Apple auth Pydantic models**

Add to the end of `hestia/api/schemas/auth.py`:

```python
class AppleRegisterRequest(BaseModel):
    """Request to register a device using Sign in with Apple."""
    identity_token: str = Field(..., description="Apple identity JWT token")
    device_name: Optional[str] = Field(None, description="Device name")
    device_type: Optional[str] = Field(None, description="Device type (ios/macos)")


class AppleRegisterResponse(BaseModel):
    """Response after Apple-based registration."""
    device_id: str = Field(description="Assigned device identifier")
    token: str = Field(description="JWT device token for authentication")
    expires_at: str = Field(description="Token expiration time (ISO8601 string)")
    server_url: str = Field(description="Server base URL")
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from hestia.api.schemas import AppleRegisterRequest, AppleRegisterResponse; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add hestia/api/schemas/auth.py
git commit -m "feat(auth): add Apple Sign In request/response schemas"
```

---

## Task 2: Backend — Database Migration for `apple_user_id`

**Files:**
- Modify: `hestia/api/invite_store.py`
- Create: `tests/test_auth_apple.py`

- [ ] **Step 1: Write migration test**

Create `tests/test_auth_apple.py`:

```python
"""Tests for Apple Sign In authentication."""

import pytest
from hestia.api.invite_store import get_invite_store


@pytest.mark.asyncio
async def test_apple_user_id_migration():
    """Verify apple_user_id column is added to registered_devices."""
    store = await get_invite_store()

    cursor = await store._connection.execute(
        "PRAGMA table_info(registered_devices)"
    )
    columns = await cursor.fetchall()
    column_names = [col["name"] for col in columns]

    assert "apple_user_id" in column_names


@pytest.mark.asyncio
async def test_register_device_with_apple_id():
    """Verify device registration stores apple_user_id."""
    store = await get_invite_store()

    device_id = "test-apple-device-001"
    await store.register_device(
        device_id=device_id,
        device_name="Test iPhone",
        device_type="ios",
        apple_user_id="000123.abc456.789",
    )

    # Verify lookup by apple_user_id
    found = await store.find_device_by_apple_id("000123.abc456.789")
    assert found is not None
    assert found["device_id"] == device_id

    # Cleanup
    await store._connection.execute(
        "DELETE FROM registered_devices WHERE device_id = ?", (device_id,)
    )
    await store._connection.commit()


@pytest.mark.asyncio
async def test_find_device_by_apple_id_not_found():
    """Verify None returned for unknown apple_user_id."""
    store = await get_invite_store()
    found = await store.find_device_by_apple_id("nonexistent.id")
    assert found is None


@pytest.mark.asyncio
async def test_find_device_by_apple_id_revoked():
    """Verify revoked device not returned by apple_user_id lookup."""
    store = await get_invite_store()

    device_id = "test-apple-revoked-001"
    apple_id = "000999.revoked.test"
    await store.register_device(
        device_id=device_id,
        device_name="Revoked iPhone",
        device_type="ios",
        apple_user_id=apple_id,
    )

    # Revoke the device
    await store._connection.execute(
        "UPDATE registered_devices SET revoked_at = ? WHERE device_id = ?",
        (datetime.now(timezone.utc).isoformat(), device_id),
    )
    await store._connection.commit()

    # Should NOT find revoked device
    found = await store.find_device_by_apple_id(apple_id)
    assert found is None

    # Cleanup
    await store._connection.execute(
        "DELETE FROM registered_devices WHERE device_id = ?", (device_id,)
    )
    await store._connection.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth_apple.py -v`
Expected: FAIL (apple_user_id column doesn't exist, methods don't exist)

- [ ] **Step 3: Add migration to invite_store.py**

Add after the `_migrate_revoked_at` call in `initialize()` (~line 77):

```python
        await self._migrate_apple_user_id()
```

Add new migration method after `_migrate_revoked_at`:

```python
    async def _migrate_apple_user_id(self) -> None:
        """Add apple_user_id column to registered_devices if it doesn't exist."""
        cursor = await self._connection.execute(
            "PRAGMA table_info(registered_devices)"
        )
        columns = await cursor.fetchall()
        column_names = [col["name"] for col in columns]

        if "apple_user_id" not in column_names:
            await self._connection.execute(
                "ALTER TABLE registered_devices ADD COLUMN apple_user_id TEXT"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_devices_apple_user_id "
                "ON registered_devices(apple_user_id)"
            )
            await self._connection.commit()
            self.logger.info(
                "Migrated registered_devices: added apple_user_id column",
                component=LogComponent.SECURITY,
            )
```

- [ ] **Step 4: Update `register_device` to accept `apple_user_id`**

In `invite_store.py`, modify the `register_device` method (line ~197):

```python
    async def register_device(
        self,
        device_id: str,
        device_name: str,
        device_type: str,
        invite_nonce: Optional[str] = None,
        apple_user_id: Optional[str] = None,
    ) -> None:
        """Register a device in the registry."""
        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """INSERT OR REPLACE INTO registered_devices
               (device_id, device_name, device_type, registered_at, invite_nonce, apple_user_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (device_id, device_name, device_type, now, invite_nonce, apple_user_id),
        )
        await self._connection.commit()
```

- [ ] **Step 5: Add `find_device_by_apple_id` lookup method**

Add after `register_device`:

```python
    async def find_device_by_apple_id(self, apple_user_id: str) -> Optional[dict]:
        """Find a registered device by Apple user identifier."""
        cursor = await self._connection.execute(
            "SELECT * FROM registered_devices WHERE apple_user_id = ? AND revoked_at IS NULL",
            (apple_user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_auth_apple.py -v`
Expected: 4 PASS (migration, register, not_found, revoked)

- [ ] **Step 7: Commit**

```bash
git add hestia/api/invite_store.py tests/test_auth_apple.py
git commit -m "feat(auth): add apple_user_id column migration and lookup"
```

---

## Task 3: Backend — Apple JWT Validation + Endpoint

**Files:**
- Modify: `hestia/api/routes/auth.py`
- Modify: `tests/test_auth_apple.py`

- [ ] **Step 1: Write endpoint tests**

Append to `tests/test_auth_apple.py`:

```python
import json
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from hestia.api.server import create_app


@pytest.fixture
def mock_apple_jwt_payload():
    """Mock decoded Apple identity token payload."""
    return {
        "iss": "https://appleid.apple.com",
        "aud": "com.andrewlonati.hestia",
        "exp": 9999999999,
        "sub": "000123.testuser.apple",
        "email": "andrew@example.com",
    }


@pytest.mark.asyncio
async def test_register_with_apple_success(mock_apple_jwt_payload):
    """Test successful Apple Sign In registration."""
    app = create_app()

    with patch("hestia.api.routes.auth.verify_apple_identity_token") as mock_verify:
        mock_verify.return_value = mock_apple_jwt_payload

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://test") as client:
            response = await client.post(
                "/v1/auth/register-with-apple",
                json={
                    "identity_token": "fake.jwt.token",
                    "device_name": "Test iPhone",
                    "device_type": "ios",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "device_id" in data
        assert "server_url" in data


@pytest.mark.asyncio
async def test_register_with_apple_invalid_token():
    """Test rejection of invalid Apple token."""
    app = create_app()

    with patch("hestia.api.routes.auth.verify_apple_identity_token") as mock_verify:
        mock_verify.side_effect = ValueError("Invalid token")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://test") as client:
            response = await client.post(
                "/v1/auth/register-with-apple",
                json={
                    "identity_token": "invalid.jwt.token",
                    "device_name": "Test iPhone",
                    "device_type": "ios",
                },
            )

        assert response.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_auth_apple.py::test_register_with_apple_success -v`
Expected: FAIL (endpoint doesn't exist)

- [ ] **Step 3: Implement Apple JWT validation helper**

Add to `hestia/api/routes/auth.py` (after imports):

```python
import httpx
from jose import jwt as jose_jwt, JWTError

# Apple public keys cache
_apple_keys_cache: Optional[dict] = None
_apple_keys_fetched_at: Optional[float] = None
_APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_ISSUER = "https://appleid.apple.com"
_APPLE_AUDIENCE = "com.andrewlonati.hestia"


async def _fetch_apple_public_keys() -> dict:
    """Fetch Apple's public keys for JWT verification."""
    global _apple_keys_cache, _apple_keys_fetched_at
    async with httpx.AsyncClient() as client:
        resp = await client.get(_APPLE_KEYS_URL, timeout=10.0)
        resp.raise_for_status()
        _apple_keys_cache = resp.json()
        _apple_keys_fetched_at = datetime.now(timezone.utc).timestamp()
        return _apple_keys_cache


async def _get_apple_public_keys(force_refresh: bool = False) -> dict:
    """Get Apple public keys with cache-then-refresh-on-miss strategy."""
    global _apple_keys_cache, _apple_keys_fetched_at
    if _apple_keys_cache is None or force_refresh:
        return await _fetch_apple_public_keys()
    # Refresh daily
    age = datetime.now(timezone.utc).timestamp() - (_apple_keys_fetched_at or 0)
    if age > 86400:
        return await _fetch_apple_public_keys()
    return _apple_keys_cache


async def verify_apple_identity_token(identity_token: str) -> dict:
    """
    Verify an Apple identity token JWT.

    Returns the decoded payload with sub, email, etc.
    Raises ValueError on any validation failure.
    """
    try:
        # Decode header to get kid
        header = jose_jwt.get_unverified_header(identity_token)
        kid = header.get("kid")
        if not kid:
            raise ValueError("Missing kid in token header")

        # Get Apple's public keys
        keys = await _get_apple_public_keys()

        # Find matching key
        matching_key = None
        for key in keys.get("keys", []):
            if key.get("kid") == kid:
                matching_key = key
                break

        # Cache miss — try refreshing
        if matching_key is None:
            keys = await _get_apple_public_keys(force_refresh=True)
            for key in keys.get("keys", []):
                if key.get("kid") == kid:
                    matching_key = key
                    break

        if matching_key is None:
            raise ValueError(f"No matching Apple public key for kid={kid}")

        # Verify and decode
        payload = jose_jwt.decode(
            identity_token,
            matching_key,
            algorithms=["RS256"],
            audience=_APPLE_AUDIENCE,
            issuer=_APPLE_ISSUER,
        )

        return payload

    except JWTError as e:
        raise ValueError(f"Apple token verification failed: {e}")
```

- [ ] **Step 4: Implement the endpoint**

Add to `hestia/api/routes/auth.py`:

```python
from hestia.api.schemas import AppleRegisterRequest, AppleRegisterResponse
from typing import Optional

# Rate limiting for Apple auth
_apple_auth_attempts: dict = {}  # ip -> [timestamps]
_APPLE_AUTH_RATE_LIMIT = 10  # per hour


def _check_apple_rate_limit(ip: str) -> bool:
    """Check rate limit for Apple auth attempts."""
    now = datetime.now(timezone.utc).timestamp()
    attempts = _apple_auth_attempts.get(ip, [])
    # Prune old attempts
    attempts = [t for t in attempts if now - t < 3600]
    _apple_auth_attempts[ip] = attempts
    return len(attempts) < _APPLE_AUTH_RATE_LIMIT


@router.post(
    "/register-with-apple",
    response_model=AppleRegisterResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid Apple identity token"},
        403: {"model": ErrorResponse, "description": "Apple ID not recognized"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    summary="Register device with Apple Sign In",
    description="Register a new device using Sign in with Apple identity token.",
)
async def register_with_apple(request: AppleRegisterRequest) -> AppleRegisterResponse:
    """
    Register a device using Apple Sign In identity token.

    Validates the Apple JWT, matches the sub claim to registered users,
    and issues a device token.
    """
    # Rate limiting
    # Note: In production behind reverse proxy, use X-Forwarded-For
    if not _check_apple_rate_limit("default"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
        )

    # Track attempt
    now = datetime.now(timezone.utc).timestamp()
    _apple_auth_attempts.setdefault("default", []).append(now)

    # Verify Apple identity token
    try:
        payload = await verify_apple_identity_token(request.identity_token)
    except ValueError as e:
        logger.warning(
            "Apple token verification failed",
            component=LogComponent.SECURITY,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired Apple identity token.",
        )

    apple_sub = payload.get("sub")
    apple_email = payload.get("email")

    if not apple_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apple identity token missing subject claim.",
        )

    store = await get_invite_store()

    # Primary: look up by apple_user_id
    existing = await store.find_device_by_apple_id(apple_sub)

    if existing:
        # Re-registration of known Apple user — issue new device token
        device_id = f"device-{uuid4().hex[:12]}"
    else:
        # New Apple user — require existing registration via setup secret first
        # (prevents unauthorized TestFlight users from claiming ownership)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Hestia account linked to this Apple ID. "
                   "Register via QR code first, then use Apple Sign In for future devices.",
        )

    device_name = request.device_name or "Unknown"
    device_type = request.device_type or "ios"
    device_info = {"device_name": device_name, "device_type": device_type}

    token, expires_at = create_device_token(device_id, device_info)

    await store.register_device(
        device_id=device_id,
        device_name=device_name,
        device_type=device_type,
        apple_user_id=apple_sub,
    )

    server_url = os.environ.get("HESTIA_SERVER_URL", "https://hestia-3.local:8443")

    logger.info(
        "Device registered via Apple Sign In",
        component=LogComponent.SECURITY,
        data={
            "device_id": device_id,
            "device_type": device_type,
            "apple_sub": apple_sub[:8] + "...",
        },
    )

    return AppleRegisterResponse(
        device_id=device_id,
        token=token,
        expires_at=expires_at,
        server_url=server_url,
    )
```

- [ ] **Step 5: Run all Apple auth tests**

Run: `python -m pytest tests/test_auth_apple.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -x --timeout=30`
Expected: All existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add hestia/api/routes/auth.py tests/test_auth_apple.py
git commit -m "feat(auth): add POST /v1/auth/register-with-apple endpoint"
```

---

## Task 4: iOS — Sign in with Apple Entitlement + Framework

**Files:**
- Modify: `HestiaApp/iOS/HestiaApp.entitlements`
- Modify: `HestiaApp/project.yml`

- [ ] **Step 1: Add Sign in with Apple entitlement**

Add to `HestiaApp/iOS/HestiaApp.entitlements` inside the `<dict>`:

```xml
	<key>com.apple.developer.applesignin</key>
	<array>
		<string>Default</string>
	</array>
```

- [ ] **Step 2: Add AuthenticationServices framework to project.yml**

In `project.yml`, under the iOS target's `dependencies:` section, add:

```yaml
        - framework: AuthenticationServices.framework
```

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/iOS/HestiaApp.entitlements HestiaApp/project.yml
git commit -m "feat(ios): add Sign in with Apple entitlement and framework"
```

---

## Task 5: iOS — AuthService Apple Registration Method

**Files:**
- Modify: `HestiaShared/Sources/HestiaShared/Auth/AuthService.swift`
- Modify: `HestiaShared/Sources/HestiaShared/Networking/APIClient.swift`

- [ ] **Step 1: Add Apple registration API call to APIClient**

In `APIClient.swift`, add a method alongside existing `registerWithInvite`:

```swift
    /// Register device using Apple Sign In identity token
    public func registerWithApple(
        identityToken: String,
        deviceName: String,
        deviceType: String
    ) async throws -> InviteRegisterResponse {
        struct AppleRegisterBody: Encodable {
            let identity_token: String
            let device_name: String
            let device_type: String
        }

        let body = AppleRegisterBody(
            identity_token: identityToken,
            device_name: deviceName,
            device_type: deviceType
        )

        let response: InviteRegisterResponse = try await post(
            "/v1/auth/register-with-apple",
            body: body
        )
        return response
    }
```

- [ ] **Step 2: Add `registerWithApple` to AuthService**

In `AuthService.swift`, add after `registerWithInvite`:

```swift
    /// Register using Apple Sign In identity token
    public func registerWithApple(identityToken: String) async throws -> String {
        let deviceName = APIClient.deviceInfo?.deviceName ?? "Unknown"
        let deviceType = APIClient.deviceInfo?.deviceType ?? "Unknown"

        let response = try await registrationClient.registerWithApple(
            identityToken: identityToken,
            deviceName: deviceName,
            deviceType: deviceType
        )

        try saveTokenToKeychain(response.token)

        await MainActor.run {
            isDeviceRegistered = true
        }

        return response.token
    }
```

- [ ] **Step 3: Verify build compiles**

Run @hestia-build-validator for iOS target.

- [ ] **Step 4: Commit**

```bash
git add HestiaShared/Sources/HestiaShared/Auth/AuthService.swift HestiaShared/Sources/HestiaShared/Networking/APIClient.swift
git commit -m "feat(ios): add Apple Sign In registration to AuthService + APIClient"
```

---

## Task 6: iOS — HestiaOrbView (Canvas + TimelineView)

**Files:**
- Create: `HestiaApp/Shared/Views/Common/HestiaOrbView.swift`

This is the 2-day time-boxed spike. Build a fluid animated orb using SwiftUI Canvas.

- [ ] **Step 1: Create HestiaOrbView with state machine**

Create `HestiaApp/Shared/Views/Common/HestiaOrbView.swift`:

```swift
import SwiftUI
import HestiaShared

/// Animated orb state — drives visual behavior
enum HestiaOrbState: Equatable {
    case idle
    case thinking
    case success
    case listening
}

/// Reusable animated orb using SwiftUI Canvas + TimelineView.
/// Renders a fluid, luminous sphere with organic motion.
struct HestiaOrbView: View {
    let state: HestiaOrbState
    var size: CGFloat = 150
    var audioLevel: CGFloat = 0.0
    var primaryColor: Color = Color(hex: "E0A050")
    var secondaryColor: Color = Color(hex: "A54B17")

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        if reduceMotion {
            staticFallback
        } else {
            animatedOrb
        }
    }

    // MARK: - Animated Orb

    private var animatedOrb: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0)) { timeline in
            let time = timeline.date.timeIntervalSinceReferenceDate

            Canvas { context, canvasSize in
                let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height / 2)
                let radius = min(canvasSize.width, canvasSize.height) / 2

                // Speed multiplier based on state
                let speed: Double = {
                    switch state {
                    case .idle: return 0.3
                    case .thinking: return 0.8
                    case .success: return 1.5
                    case .listening: return 0.4 + Double(audioLevel) * 0.6
                    }
                }()

                let t = time * speed

                // Draw layered noise circles for fluid effect
                for layer in 0..<8 {
                    let layerF = CGFloat(layer)
                    let phase = t + Double(layer) * 0.7

                    // Noise-based displacement for organic motion
                    let dx = CGFloat(sin(phase * 1.3 + layerF * 0.5)) * radius * 0.08
                    let dy = CGFloat(cos(phase * 0.9 + layerF * 0.3)) * radius * 0.08

                    // Layer radius shrinks toward center
                    let layerRadius = radius * (1.0 - layerF * 0.06) + CGFloat(sin(phase * 2.0 + layerF)) * radius * 0.02

                    // Color interpolation: outer layers darker, inner brighter
                    let brightness = 0.15 + (1.0 - layerF / 8.0) * 0.85
                    let opacity = 0.3 + (1.0 - layerF / 8.0) * 0.5

                    // Warm amber gradient per layer
                    let r = min(1.0, 0.88 * brightness + layerF * 0.01)
                    let g = min(1.0, 0.63 * brightness - layerF * 0.02)
                    let b = min(1.0, 0.31 * brightness - layerF * 0.01)

                    let color = Color(red: r, green: g, blue: b).opacity(opacity)

                    let layerCenter = CGPoint(
                        x: center.x + dx,
                        y: center.y + dy
                    )

                    let ellipse = Path(ellipseIn: CGRect(
                        x: layerCenter.x - layerRadius,
                        y: layerCenter.y - layerRadius,
                        width: layerRadius * 2,
                        height: layerRadius * 2
                    ))

                    context.fill(ellipse, with: .color(color))
                }

                // Inner highlight (specular)
                let highlightOffset = CGPoint(
                    x: center.x - radius * 0.2 + CGFloat(sin(t * 0.5)) * radius * 0.05,
                    y: center.y - radius * 0.25 + CGFloat(cos(t * 0.4)) * radius * 0.05
                )
                let highlightRadius = radius * 0.35
                let highlight = Path(ellipseIn: CGRect(
                    x: highlightOffset.x - highlightRadius,
                    y: highlightOffset.y - highlightRadius,
                    width: highlightRadius * 2,
                    height: highlightRadius * 2
                ))
                context.fill(highlight, with: .color(.white.opacity(0.12)))

                // Outer glow via larger, faint circle
                let glowRadius = radius * 1.3
                let glowRect = CGRect(
                    x: center.x - glowRadius,
                    y: center.y - glowRadius,
                    width: glowRadius * 2,
                    height: glowRadius * 2
                )
                let glowGradient = Gradient(colors: [
                    Color(red: 0.88, green: 0.63, blue: 0.31).opacity(0.15),
                    Color(red: 0.88, green: 0.63, blue: 0.31).opacity(0.0),
                ])
                context.fill(
                    Path(ellipseIn: glowRect),
                    with: .radialGradient(
                        glowGradient,
                        center: center,
                        startRadius: radius * 0.8,
                        endRadius: glowRadius
                    )
                )
            }
            .frame(width: size, height: size)
        }
    }

    // MARK: - Reduce Motion Fallback

    private var staticFallback: some View {
        Circle()
            .fill(
                RadialGradient(
                    colors: [
                        Color(hex: "FFE0A8"),
                        Color(hex: "E0A050"),
                        Color(hex: "A54B17"),
                        Color(hex: "8B3A0F").opacity(0.3),
                    ],
                    center: UnitPoint(x: 0.35, y: 0.35),
                    startRadius: 0,
                    endRadius: size / 2
                )
            )
            .frame(width: size, height: size)
            .shadow(color: Color(hex: "E0A050").opacity(0.3), radius: 30)
    }
}

// MARK: - Preview

struct HestiaOrbView_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            VStack(spacing: 40) {
                HestiaOrbView(state: .idle)
                HestiaOrbView(state: .thinking, size: 100)
            }
        }
    }
}
```

- [ ] **Step 2: Verify build compiles**

Run @hestia-build-validator for iOS target.

- [ ] **Step 3: Visual verification**

Open Xcode previews to verify the orb renders with fluid motion. Adjust layer count, displacement amounts, and color values as needed to match the Dribbble reference aesthetic. This is the spike — iterate until it looks right.

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/Shared/Views/Common/HestiaOrbView.swift
git commit -m "feat(ui): add HestiaOrbView — Canvas-based animated fluid orb"
```

---

## Task 7: iOS — OnboardingBackground Gradient

**Files:**
- Create: `HestiaApp/Shared/Views/Common/OnboardingBackground.swift`

- [ ] **Step 1: Create atmospheric gradient background**

Create `HestiaApp/Shared/Views/Common/OnboardingBackground.swift`:

```swift
import SwiftUI
import HestiaShared

/// Dark-to-teal atmospheric gradient for onboarding screens.
/// Static (no animation) — all motion is concentrated in the orb.
struct OnboardingBackground: View {
    var body: some View {
        ZStack {
            // 12-stop linear gradient: near-black → warm dark → deep teal
            LinearGradient(
                stops: [
                    .init(color: Color(hex: "050404"), location: 0.0),
                    .init(color: Color(hex: "0A0806"), location: 0.10),
                    .init(color: Color(hex: "0D0A07"), location: 0.22),
                    .init(color: Color(hex: "0C0B09"), location: 0.35),
                    .init(color: Color(hex: "0A0C0A"), location: 0.48),
                    .init(color: Color(hex: "0A100E"), location: 0.58),
                    .init(color: Color(hex: "0C1A16"), location: 0.68),
                    .init(color: Color(hex: "10251F"), location: 0.76),
                    .init(color: Color(hex: "153028"), location: 0.83),
                    .init(color: Color(hex: "1A3B32"), location: 0.89),
                    .init(color: Color(hex: "1F453B"), location: 0.94),
                    .init(color: Color(hex: "245044"), location: 1.0),
                ],
                startPoint: .top,
                endPoint: .bottom
            )

            // Atmospheric radial glow at bottom center (use GeometryReader, not UIScreen)
            GeometryReader { geo in
            RadialGradient(
                colors: [
                    Color(hex: "2A7A6A").opacity(0.18),
                    Color(hex: "235A4C").opacity(0.10),
                    Color.clear,
                ],
                center: UnitPoint(x: 0.5, y: 1.3),
                startRadius: 0,
                endRadius: geo.size.height * 0.5
            )
            }
        }
        .ignoresSafeArea()
    }
}
```

- [ ] **Step 2: Verify build + preview**

Run @hestia-build-validator. Check Xcode preview.

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/Shared/Views/Common/OnboardingBackground.swift
git commit -m "feat(ui): add OnboardingBackground — dark-to-teal atmospheric gradient"
```

---

## Task 8: iOS — Redesigned OnboardingViewModel

**Files:**
- Replace: `HestiaApp/Shared/ViewModels/OnboardingViewModel.swift`

- [ ] **Step 1: Replace OnboardingViewModel with new state machine**

Replace the entire contents of `OnboardingViewModel.swift`:

```swift
import SwiftUI
import AuthenticationServices
import HestiaShared

/// Onboarding step state machine
enum OnboardingStep: Equatable {
    case welcome
    case appleSignIn
    case serverURL
    case connecting
    case success
    case error(String)
}

/// ViewModel for the redesigned onboarding flow
@MainActor
class OnboardingViewModel: ObservableObject {
    // MARK: - Published State

    @Published var step: OnboardingStep = .welcome
    @Published var isProcessing = false
    @Published var serverURL: String = ""
    @Published var orbState: HestiaOrbState = .idle

    // MARK: - Apple Sign In State

    private var appleIdentityToken: String?
    private var appleUserID: String?

    // MARK: - Dependencies

    private var authService: AuthService?
    private var apiClientProvider: APIClientProvider?

    // MARK: - Configuration

    func configure(authService: AuthService, apiClientProvider: APIClientProvider) {
        self.authService = authService
        self.apiClientProvider = apiClientProvider
        prefillServerURL()
    }

    // MARK: - Actions

    func getStartedTapped() {
        step = .appleSignIn
    }

    /// Handle Apple Sign In result
    func handleAppleSignIn(result: Result<ASAuthorization, Error>) {
        switch result {
        case .success(let authorization):
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData = credential.identityToken,
                  let token = String(data: tokenData, encoding: .utf8) else {
                step = .error("Could not read Apple credentials.")
                return
            }

            appleIdentityToken = token
            appleUserID = credential.user

            // Move to server URL step
            step = .serverURL
            orbState = .idle

        case .failure(let error):
            let nsError = error as NSError
            if nsError.code == ASAuthorizationError.canceled.rawValue {
                // User cancelled — go back silently
                step = .welcome
            } else {
                step = .error("Apple Sign In failed. Please try again.")
            }
        }
    }

    /// Connect to server with provided URL
    func connectToServer() {
        guard !serverURL.isEmpty else { return }
        guard let token = appleIdentityToken else {
            step = .error("Apple credentials missing. Please start over.")
            return
        }

        Task {
            await registerWithServer(identityToken: token)
        }
    }

    /// Handle QR code scan (escape hatch)
    func handleScannedCode(_ code: String) {
        guard let data = code.data(using: .utf8),
              let payload = try? JSONDecoder().decode(QRInvitePayload.self, from: data) else {
            step = .error("Invalid QR code.")
            return
        }

        serverURL = payload.u

        Configuration.shared.configureFromQR(
            serverURL: payload.u,
            certFingerprint: payload.f
        )

        Task {
            await registerWithInvite(payload: payload)
        }
    }

    func retry() {
        step = .serverURL
        orbState = .idle
    }

    func goBack() {
        step = .welcome
        orbState = .idle
        appleIdentityToken = nil
    }

    // MARK: - Private

    private func prefillServerURL() {
        // Check last known URL
        if let lastURL = UserDefaults.standard.string(forKey: "hestia_server_url"),
           !lastURL.isEmpty {
            serverURL = lastURL
            return
        }

        // Try Tailscale MagicDNS resolution
        Task {
            if await resolvesTailscaleHost() {
                serverURL = "https://hestia-3.local:8443"
            }
        }
    }

    private func resolvesTailscaleHost() async -> Bool {
        // Attempt DNS resolution of the Tailscale hostname
        return await withCheckedContinuation { continuation in
            let host = CFHostCreateWithName(nil, "hestia-3.local" as CFString).takeRetainedValue()
            var resolved = DarwinBoolean(false)
            CFHostStartInfoResolution(host, .addresses, nil)
            if let _ = CFHostGetAddressing(host, &resolved)?.takeUnretainedValue() as? [Data],
               resolved.boolValue {
                continuation.resume(returning: true)
            } else {
                continuation.resume(returning: false)
            }
        }
    }

    private func registerWithServer(identityToken: String) async {
        guard let authService = authService else {
            step = .error("Auth service not available.")
            return
        }

        isProcessing = true
        step = .connecting
        orbState = .thinking

        // Configure API to point at the entered server URL
        let url = serverURL.hasPrefix("https://") ? serverURL : "https://\(serverURL)"
        // Use configureFromQR — empty fingerprint allows first connection
        // to establish cert pinning on success
        Configuration.shared.configureFromQR(serverURL: url, certFingerprint: "")

        // Save for next time
        UserDefaults.standard.set(url, forKey: "hestia_server_url")

        do {
            let token = try await authService.registerWithApple(identityToken: identityToken)
            apiClientProvider?.configure(withToken: token)

            #if DEBUG
            print("[OnboardingVM] Apple registration successful")
            #endif

            orbState = .success

            // Brief delay for success animation, then transition
            try? await Task.sleep(nanoseconds: 1_200_000_000)
            step = .success
        } catch {
            #if DEBUG
            print("[OnboardingVM] Apple registration failed: \(error)")
            #endif

            orbState = .idle

            let message: String
            if let hestiaError = error as? HestiaError {
                message = hestiaError.userMessage
            } else {
                message = "Could not connect to server. Check the URL and try again."
            }
            step = .error(message)
        }

        isProcessing = false
    }

    private func registerWithInvite(payload: QRInvitePayload) async {
        guard let authService = authService else { return }

        isProcessing = true
        step = .connecting
        orbState = .thinking

        do {
            let token = try await authService.registerWithInvite(inviteToken: payload.t)
            apiClientProvider?.configure(withToken: token)
            orbState = .success
            try? await Task.sleep(nanoseconds: 1_200_000_000)
            step = .success
        } catch {
            orbState = .idle
            let message = (error as? HestiaError)?.userMessage
                ?? "Could not connect. Check QR code and try again."
            step = .error(message)
        }

        isProcessing = false
    }
}
```

- [ ] **Step 2: Verify build compiles**

Run @hestia-build-validator.

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/Shared/ViewModels/OnboardingViewModel.swift
git commit -m "feat(ui): redesigned OnboardingViewModel with Apple auth + smart URL"
```

---

## Task 9: iOS — Redesigned OnboardingView

**Files:**
- Replace: `HestiaApp/Shared/Views/Auth/OnboardingView.swift`

- [ ] **Step 1: Replace OnboardingView with new design**

Replace `OnboardingView.swift`. Key sections:
- `welcomeStep`: OnboardingBackground + HestiaOrbView(.idle) + title + "Get Started" pill button
- `serverURLStep`: Orb + frosted-glass text field (pre-filled) + "Connect" + "Scan QR code" footer
- `connectingStep`: Orb(.thinking) + SnarkyBylineView
- `successStep`: Orb(.success) + animated offset/opacity exit
- `errorStep`: Error message + "Try Again"
- Apple Sign In presented via `SignInWithAppleButton` overlay when step == .appleSignIn

Use the Liquid Glass button style: frosted blur, layered borders, pill shape (`Capsule()`), teal underglow.

The full view implementation follows the mockup at `docs/superpowers/specs/2026-03-25-onboarding-redesign-design.md` — dark atmospheric background, centered orb+title in upper 60%, pill button in lower 25%.

- [ ] **Step 2: Verify build + preview**

Run @hestia-build-validator. Check Xcode preview for all steps.

- [ ] **Step 3: Update ContentView.swift routing**

In `ContentView.swift`, update `RootView` to handle the success transition — when onboarding completes, the view switches to `MainTabView`. Add a brief crossfade transition:

```swift
if !authService.isDeviceRegistered {
    OnboardingView()
        .transition(.opacity.animation(.easeInOut(duration: 0.5)))
}
```

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/Shared/Views/Auth/OnboardingView.swift HestiaApp/Shared/App/ContentView.swift
git commit -m "feat(ui): redesigned onboarding — dark atmospheric + Apple Sign In + smart URL"
```

---

## Task 10: Integration Testing + Polish

**Files:**
- Various (testing + cleanup)

- [ ] **Step 1: Run full backend test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All pass including new Apple auth tests.

- [ ] **Step 2: Run iOS build validation**

Run @hestia-build-validator for both iOS and macOS targets.

- [ ] **Step 3: Manual flow testing on device/simulator**

Test all paths:
1. Fresh install → welcome → Get Started → Apple Sign In → server URL (pre-filled) → connect → success
2. Fresh install → welcome → Get Started → Apple Sign In → cancel → back to welcome
3. Fresh install → welcome → Get Started → Apple Sign In → wrong server URL → error → retry
4. Fresh install → welcome → Get Started → Apple Sign In → QR code fallback → success
5. Verify Reduce Motion fallback shows static orb

- [ ] **Step 4: Add orb exit animation**

In the success step, animate the orb upward with:
```swift
.offset(y: step == .success ? -UIScreen.main.bounds.height : 0)
.opacity(step == .success ? 0 : 1)
.animation(.easeIn(duration: 0.8), value: step)
```

- [ ] **Step 5: Run @hestia-reviewer on all changed files**

- [ ] **Step 6: Final commit**

Stage all changed files explicitly (verify with `git status` first), then:
```bash
git commit -m "feat: onboarding integration polish — animation + flow testing"
```

---

## Apple Developer Portal Setup (Manual — Andrew)

Before the Apple Sign In flow works, Andrew must:
1. Go to [Apple Developer Portal](https://developer.apple.com/account)
2. Navigate to Certificates, Identifiers & Profiles → Identifiers
3. Select the `com.andrewlonati.hestia` App ID
4. Enable "Sign in with Apple" capability
5. Save

And for the first device registration:
1. Use the existing QR flow (or manual URL) to register the first device
2. Then link Apple ID: the server stores the `apple_user_id` in the device record
3. Future devices can use Apple Sign In directly

---

## Summary

| Task | Effort | Risk |
|------|--------|------|
| 1. Backend schemas | 10 min | None |
| 2. DB migration | 30 min | Low |
| 3. Backend endpoint | 1-2 hr | Medium (Apple JWT validation) |
| 4. iOS entitlements | 10 min | None |
| 5. AuthService methods | 30 min | Low |
| 6. HestiaOrbView spike | 4-8 hr | Medium (visual quality) |
| 7. OnboardingBackground | 20 min | None |
| 8. OnboardingViewModel | 1-2 hr | Low |
| 9. OnboardingView | 2-3 hr | Medium (UI polish) |
| 10. Integration + polish | 2-3 hr | Low |
| **Total** | **~12-20 hr** | |
