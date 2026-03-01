# Plan Audit: Wire Frontend to Backend — DevOps → Explorer → Command
**Date:** 2026-02-28
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary
3-sprint plan to wire Hestia's iOS + macOS frontends to the backend: Sprint 1 adds QR code onboarding + permissions, Sprint 2 builds a unified Explorer resource canvas, Sprint 3 rewrites the Command Center as a newsfeed.

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Follows all established patterns (Manager, APIClient extensions, HestiaShared SPM). All Explorer assumptions validated. Mature Apple CLI tools (20 handlers). Sequential ordering reduces risk. | **Weaknesses:** Sprint 2 scope is large (5 resource types + 2 platforms). No proactive.yaml exists. Briefing endpoint never called from iOS. No caching strategy in original plan. |
| **External** | **Opportunities:** Orders `hestia_read` field perfect for newsfeed. Existing file tools can be exposed with minimal wrappers. macOS Explorer has file browser foundation. | **Threats:** Mail requires Full Disk Access (OS permission). RSS `feedparser` introduces content parsing surface. QR setup_secret loss = lockout without recovery. |

## CISO Review
**Verdict:** Needs Remediation
- **CRITICAL-1:** Open `/v1/auth/register` accepts any device. QR onboarding adds gate but doesn't close existing hole.
- **CRITICAL-2:** No setup_secret recovery mechanism.
- **HIGH-1:** No rate limiting on invite generation.
- **HIGH-2:** RSS feed content → LLM summarization = prompt injection vector.
- **Acceptable:** QR JWT payload, nonce one-time-use, Keychain SYSTEM tier.

## CTO Review
**Verdict:** Needs Remediation
- **HIGH-1:** Explorer aggregation via subprocess-based Apple CLI tools with no caching.
- **HIGH-2:** Plan references non-existent `proactive.yaml`.
- **HIGH-3:** Hybrid dedup (backend + frontend) with fragile ID generation.
- **Acceptable:** Module structure, LogComponent extension, route registration.

## CPO Review
**Verdict:** Acceptable
- **HIGH-1:** Sprint 2 scope ambitious for ~3 sessions.
- **HIGH-2:** BriefingCard in plan but iOS has never called `/v1/proactive/briefing`.
- **Acceptable:** QR onboarding value, sequential ordering, newsfeed concept.

## Conditions for Approval (all addressed in updated plan)

1. CISO-C1: Deprecate open registration via `require_invite` config flag
2. CISO-C2: Added `/v1/auth/re-invite` recovery endpoint
3. CISO-H1: Rate limit invites (5/hour)
4. CISO-H2: RSS content sanitization before LLM
5. CTO-H1: TTL cache layer in Explorer database.py
6. CTO-H2: Use config_store.py pattern for RSS config
7. CTO-H3: Explicit ID generation rules, backend authoritative
8. CPO-H1: Monitor velocity, defer macOS Explorer if needed
9. CPO-H2: Added briefing APIClient method + models

## Final Critiques
1. **Most likely failure:** Explorer aggregation performance. Mitigated by TTL cache.
2. **Critical assumption:** Apple CLI tools can aggregate in <2s. Validate with timing benchmark.
3. **Half-time cut list:** macOS Explorer (2D), content preview beyond Markdown (2C), RSS endpoints (3B).
