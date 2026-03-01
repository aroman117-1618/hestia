# Plan Audit: Hestia Cleanup Batch — Research, Audit, and Parallel Execution

**Date:** 2026-03-01
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Post-audit cleanup batch: trim dead Swift code (Constants.swift, 11 unguarded prints), delete dead Python module (persona/), archive stale docs, add 22 missing API contract endpoints, document agents v1/v2 coexistence (ADR-031), and refresh CLAUDE.md counts. All work is independent of the Sprint 3 / Mac Mini session running in parallel.

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Thorough pre-research eliminated 4 of 8 original audit items (already fixed). Remaining scope is tight (13 files, all verified). Worktree isolation prevents cross-contamination. Zero file overlap with Sprint 3. | **Weaknesses:** Worktree merge of 3 parallel agents modifying different file types adds git choreography complexity. Documentation batch (22 endpoints) requires reading 3 route files carefully — highest error surface. CLAUDE.md is also modified by Sprint 3 session → potential merge conflict on counts. |
| **External** | **Opportunities:** Explorer discovered `Constants.Limits.maxPendingReviews` and `sessionTimeoutSeconds` are also dead — can trim Limits enum further. Test file count in CLAUDE.md is also stale (23, not 20). | **Threats:** Other session may commit CLAUDE.md changes (Sprint 3 endpoint additions) between our edit and push — race condition on shared doc. |

---

## CISO Review

**Verdict: Acceptable**

### Security Assessment

| Change | Risk | Assessment |
|--------|------|-----------|
| Delete dead Constants.swift code (API keys, storage keys, keychain config) | Positive | Removes dead credential-adjacent constants that could confuse future developers into using insecure patterns (hardcoded `http://` baseURL, generic keychain service ID) |
| Wrap print() in `#if DEBUG` | Positive | Prevents leaking internal state (API URLs, config changes, user input text) in production builds |
| Delete persona/ module | Neutral | Empty module, zero attack surface change |
| Archive phase-6-gaps.md | Neutral | Documentation only |
| API contract update | Neutral | Documentation only, no code change |
| ADR-031 (agents coexistence) | Positive | Documents that v1 is the iOS auth surface — important for future security reviews |
| CLAUDE.md refresh | Neutral | Accuracy improvement |

**Critical issues:** None.

**Advisory:** The `MessageInputBar.swift:92` print leaks user input text (`"Sending: \(text)"`) to console in production. This is the highest-severity print to fix — prioritize it if anything gets cut.

---

## CTO Review

**Verdict: Approve with Conditions**

### Architecture Assessment

| Change | Assessment |
|--------|-----------|
| Constants.swift trim | Correct approach. Keep `Limits` (has 1 active ref), delete 4 dead enums. Do NOT delete entire file — `maxConversationHistory` is used in both ChatViewModel and MacChatViewModel. |
| 11 print wraps | Straightforward. CertificatePinning closure pattern is correct (`#if DEBUG` inside closure body). |
| persona/ deletion | Clean. Zero deps confirmed via exhaustive grep. |
| API contract (22 endpoints) | Highest-effort item. Must be generated from actual route files, not from memory. |
| ADR-031 | Well-reasoned. V1/V2 are genuinely orthogonal, not a migration debt. |

### Conditions

**CTO-C1: API contract must be generated from route file decorators, not from plan summary.**
The plan lists endpoint paths in shorthand. The agent writing the contract MUST read the actual route files (`explorer.py`, `wiki.py`, `user_profile.py`) and extract exact paths, methods, query parameters, request bodies, and response schemas from the code. Shorthand documentation leads to inaccuracies.

**CTO-C2: CLAUDE.md edit should be minimal — counts only.**
Don't restructure or rewrite CLAUDE.md sections. Change only the specific numbers (endpoint count, module count, test file count, test count). This minimizes merge conflict risk with the Sprint 3 session that may also touch CLAUDE.md.

**CTO-C3: Verify `Constants.Limits` usage before trimming further.**
The explorer claimed `maxPendingReviews` and `sessionTimeoutSeconds` are unused, but earlier research only confirmed `maxConversationHistory` as used. Verify the other two with grep before removing them. If they're dead, trim Limits to just `maxConversationHistory`. But don't delete the Limits enum itself.

---

## CPO Review

**Verdict: Acceptable**

### Value Assessment

| Change | User Value | Priority |
|--------|-----------|----------|
| Print wraps | Medium — prevents production log spam, protects user privacy (input text leak) | HIGH |
| Constants cleanup | Low — developer hygiene, no user-facing impact | LOW |
| persona/ deletion | Low — removes confusion for future sessions | LOW |
| API contract (22 endpoints) | High — enables other developers/sessions to correctly consume Explorer, Wiki, User Profile APIs | HIGH |
| ADR-031 | Medium — prevents future sessions from wasting time trying to "migrate" agents | MEDIUM |
| CLAUDE.md refresh | Medium — prevents count confusion in future sessions | MEDIUM |

### Scope Assessment

**Right-sized.** The research phase correctly eliminated 4 items that were already fixed, reducing scope from "ambitious cleanup" to "focused hygiene." The remaining work is all verified-necessary.

**Opportunity cost:** Low. This is housekeeping that doesn't compete with feature work. Sprint 3 is running in parallel.

### Priority Ordering

The plan batches by file type (Swift / Python / Docs), which optimizes for parallelism. But if batches can't all run, priority order should be:

1. Print wraps (user privacy in production)
2. API contract (enables future work)
3. ADR-031 + CLAUDE.md (institutional knowledge)
4. Dead code deletion (hygiene)

---

## Sequencing Issues

**Parallel execution is correct.** All three batches touch completely independent file sets:
- Alpha: Swift files only
- Beta: Python module + one markdown doc in `docs/`
- Gamma: Markdown docs only (api-contract, decision-log, CLAUDE.md)

No sequencing dependencies. The plan correctly identifies that CLAUDE.md module count depends on persona/ deletion, but since Gamma writes "20 modules" (the post-deletion count), both can proceed simultaneously.

**One risk:** If Gamma writes CLAUDE.md counts and the Sprint 3 session also edits CLAUDE.md (adding newsfeed endpoints), there will be a merge conflict. Mitigation: make the CLAUDE.md edit as surgical as possible (CTO-C2).

---

## Quality Gates

| Gate | Criteria | Tool |
|------|----------|------|
| Swift build | Both `xcodebuild -scheme HestiaApp` and `xcodebuild -scheme Hestia` pass | Bash |
| Python tests | 1015 pass, 3 skip, 0 fail | @hestia-tester |
| Print audit | 0 unguarded `print(` outside `#if DEBUG` | grep script |
| Import audit | 0 references to `hestia.persona` | grep |
| Doc accuracy | Endpoint counts in api-contract match actual route file decorators | @hestia-reviewer |

**Assessment:** Quality gates are well-defined and measurable. The grep-based audits are deterministic. Build and test gates catch regressions.

---

## Single Points of Failure

| Risk | Mitigation |
|------|-----------|
| Worktree merge fails (conflicting changes) | Zero file overlap verified — merge should be trivial |
| xcodebuild fails after Constants.swift deletion | Limits enum still exists with the one active reference — low risk |
| CLAUDE.md merge conflict with Sprint 3 | Make surgical edits (counts only), resolve conflict at merge time |
| API contract inaccuracies (wrong endpoint signatures) | CTO-C1 requires reading actual route files, not writing from memory |

No critical single points of failure. All changes are reversible via git.

---

## Final Critiques

1. **Most likely failure:** API contract documentation has wrong request/response schemas because the agent writes from the plan summary instead of reading the actual route files. **Mitigation:** CTO-C1 — mandate reading route files as source of truth.

2. **Critical assumption:** "No file overlap with Sprint 3." Validated by explorer — Sprint 3 touches CommandCenter views, newsfeed module, and ContentView. None of those appear in our file list. **If wrong:** Merge conflicts, but resolvable — nothing destructive.

3. **Half-time cut list:** Drop Constants.swift trim (Tier A, low value) and persona/ deletion (Tier A, low value). Keep: print wraps (privacy), API contract (enables work), ADR-031 + CLAUDE.md (institutional knowledge).

---

## Conditions for Approval

1. **CTO-C1:** API contract sections MUST be generated by reading actual route files (`explorer.py`, `wiki.py`, `user_profile.py`), not from plan shorthand. Include exact paths, methods, query params, request bodies, and response models.

2. **CTO-C2:** CLAUDE.md edit is counts-only — no structural changes. Minimize merge conflict surface with Sprint 3 session.

3. **CTO-C3:** Verify `Constants.Limits.maxPendingReviews` and `Constants.Limits.sessionTimeoutSeconds` usage with grep before deciding whether to trim Limits further or keep all three constants.
