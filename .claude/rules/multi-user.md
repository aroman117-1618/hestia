---
paths:
  - "hestia/hestia/**/*.py"
---

# Multi-User Readiness Rules

When writing or modifying Python backend code, follow these rules to maintain multi-user readiness:

1. **Include `user_id` scoping on all new database tables and queries.** Every table that stores user-specific data must have a `user_id` column, and every query must filter by it.

2. **Never assume single user.** Always filter by the authenticated user's identity from JWT claims. No global state that's implicitly per-user.

3. **Support multiple devices per user.** Sessions, push tokens, and device-specific preferences should be scoped by both `user_id` and `device_id`.

4. **Treat `device_id` as sub-identity of `user_id`, not the primary identity.** The user is the account owner; devices are access points.

5. **Store user-specific data with `user_id`, device-specific with `device_id`.** Preferences, memories, and profiles belong to the user. Tokens, sessions, and device state belong to the device.

6. **Never hardcode file paths assuming a single user's home directory.** Use config-driven paths that can be parameterized per user.

7. **Design API endpoints to be user-scoped via JWT claims.** The authenticated user's identity should determine what data is returned, not implicit global state.
