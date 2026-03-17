# Discovery Report: CI/CD Pipeline Comprehensive Fix
**Date:** 2026-03-17
**Confidence:** High
**Decision:** Fix all six CI/CD issues in a single sprint — the fixes are independent, well-understood, and mostly configuration changes.

## Hypothesis
Hestia's GitHub Actions are 100% failing. The immediate blocker is a Python version incompatibility (`backports-asyncio-runner==1.2.0` doesn't exist for Python 3.11). Beyond that, there are five additional structural issues making the entire CI/CD pipeline non-functional: unreachable deploy target, hidden test failures, insufficient Claude action permissions, no pip caching, and no Swift build validation.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Well-structured codebase with 2037 tests, existing deploy script that works locally, clear separation of CI/deploy/Claude workflows, pip-compile lockfile workflow already established | **Weaknesses:** requirements.txt compiled with Python 3.9 but CI runs 3.11, `continue-on-error: true` hides real failures, deploy.yml assumes direct SSH to private network, Claude action has read-only perms (can't comment on PRs) |
| **External** | **Opportunities:** Tailscale GitHub Action v4 enables secure ephemeral tunnel to Mac Mini from CI, pip cache built into setup-python action (already partially configured), self-hosted macOS runner could enable Swift builds | **Threats:** Tailscale OAuth setup adds a credentials management surface, self-hosted runner security exposure, pytest-asyncio major version jump (0.21 -> 1.x) may introduce breaking changes in test behavior |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **P1: Fix `backports-asyncio-runner` blocker** — CI literally cannot install deps. **P2: Remove `continue-on-error: true`** — hiding real failures defeats CI purpose. **P3: Fix Claude action permissions** — currently useless (can't comment) | **P5: Add pip caching** — already half-configured, minor speed improvement |
| **Low Priority** | **P4: Fix deploy.yml SSH via Tailscale** — deploys still work via local script. **P6: Swift build validation** — requires self-hosted macOS runner (significant infra) | (none) |

## Argue (Best Case)

**All six fixes are achievable in a single session:**

1. **P1 (backports-asyncio-runner):** Root cause is clear. `requirements.txt` was compiled with Python 3.9, which resolves `pytest-asyncio==1.2.0` → pulls `backports-asyncio-runner==1.2.0` as a transitive dep. But `backports-asyncio-runner` only published version `1.0.0` on PyPI — version `1.2.0` doesn't exist. On Python 3.11, `backports-asyncio-runner` isn't needed at all (it backports `asyncio.Runner` from 3.11). **Fix:** Re-compile `requirements.txt` with Python 3.11 (`pip-compile --python-version 3.11`), which will omit the backports package entirely via environment markers. Alternatively, pin `pytest-asyncio>=0.23.0,<1.0` in `requirements.in` to avoid the 1.x line that introduced this dep, though upgrading is better.

2. **P2 (continue-on-error):** Replace with a smarter approach — run tests without `continue-on-error`, but mark macOS-specific tests with `@pytest.mark.integration` and skip them in CI via `pytest -m "not integration"`. Only 5 tests use skip markers today; the rest mock their dependencies properly and should pass on Linux.

3. **P3 (Claude action perms):** Change from `read` to `write` for `contents`, `pull-requests`, and `issues`. This is the [documented requirement](https://github.com/anthropics/claude-code-action).

4. **P4 (Deploy via Tailscale):** Use `tailscale/github-action@v4` with OAuth client credentials to create an ephemeral node on the tailnet, then SSH normally. Requires two new secrets: `TS_OAUTH_CLIENT_ID` and `TS_OAUTH_SECRET`.

5. **P5 (pip caching):** The `setup-python` action already has `cache: 'pip'` configured — it's actually working. The lockfile freshness check runs `pip-compile` uncached (intentional). No change needed here.

6. **P6 (Swift validation):** Requires a self-hosted macOS runner (can't build Swift on ubuntu-latest). Can run on the Mac Mini itself as a self-hosted runner, or defer to local pre-push hooks (already implemented in `scripts/pre-push.sh`).

## Refute (Devil's Advocate)

**Risks of the proposed fixes:**

1. **P1:** Re-compiling with Python 3.11 means the lockfile won't install cleanly on the local dev machine running Python 3.9. The dev environment and CI environment will diverge. This is the fundamental tension — the project says `requires-python = ">=3.11,<3.13"` in CLAUDE.md but the local machine runs Python 3.9.6. **Mitigation:** Either upgrade the dev machine to Python 3.11+, or use `--python-version 3.11` flag for pip-compile while keeping 3.9 locally (pip-compile supports cross-version compilation).

2. **P2:** Removing `continue-on-error` could surface tests that genuinely fail on Linux (Keychain deps, macOS-only APIs). This could make CI red until all those tests are properly marked. **Mitigation:** Audit which tests fail on Linux before removing the flag. The three files with Keychain deps (`test_research.py`, `test_cloud.py`, `test_memory.py`) already mock their Keychain calls — they should pass.

3. **P3:** Giving Claude action `contents: write` means it could push commits. The existing security hardening (fork check, @claude mention requirement) mitigates this, but it's a wider permission surface.

4. **P4:** Tailscale OAuth requires creating an OAuth client in the Tailscale admin console and storing credentials as GitHub secrets. The ephemeral node approach is well-tested but adds a dependency on Tailscale's infrastructure being available during CI.

5. **P6:** Self-hosted runners introduce maintenance burden and security considerations. The Mac Mini is already running the production Hestia server — running CI on it adds load.

## Third-Party Evidence

- **Tailscale GitHub Action** is the [official recommended approach](https://tailscale.com/kb/1276/tailscale-github-action) for connecting CI to private infrastructure. Used by thousands of repos. OAuth + ephemeral nodes is the preferred auth method over static auth keys.
- **pip-compile cross-version:** `pip-compile --python-version 3.11` generates environment-marker-aware lockfiles that work across versions. This is the [pip-tools recommended approach](https://github.com/jazzband/pip-tools#cross-environment-usage).
- **claude-code-action permissions:** The [official docs](https://github.com/anthropics/claude-code-action) specify `contents: write`, `pull-requests: write`, `issues: write` as required permissions.
- **pytest-asyncio 1.x:** The 1.0+ line (May 2025+) conditionally depends on `backports-asyncio-runner` only for Python <3.11. On 3.11+, the dep is excluded via markers. The bug is that pip-compile on 3.9 resolves the dep unconditionally and pins it without markers.

## Recommendation

Execute fixes in this order (each is independently committable):

### Fix 1: Re-compile requirements.txt for Python 3.11 (IMMEDIATE)
```bash
pip-compile requirements.in --output-file=requirements.txt --no-emit-index-url --python-version 3.11
```
This eliminates `backports-asyncio-runner` and `backports-tarfile` from the lockfile (they're Python <3.11 backports). The lockfile will still install on 3.9 for packages without markers, but the CI-blocking packages will be gone.

**Alternative (safer):** Pin `pytest-asyncio>=0.23.0,<1.0` in `requirements.in` to stay on 0.x which never added the backports dep. Less ideal long-term but zero risk of breaking local dev.

**Recommended approach:** Use `--python-version 3.11` flag. If local dev breaks, that's a signal to upgrade the dev machine Python (CLAUDE.md already says `>=3.11`).

### Fix 2: Remove continue-on-error, add proper test filtering (IMMEDIATE)
```yaml
- name: Run tests
  run: python -m pytest tests/ --tb=short -q --timeout=30 -m "not integration"
```
Remove `continue-on-error: true`. Tests that need Ollama/Keychain are already mocked or marked `integration`.

### Fix 3: Fix Claude action permissions (IMMEDIATE)
```yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
  id-token: write
```
Minimum: `pull-requests: write` for commenting. `contents: read` is sufficient (Claude shouldn't push).

### Fix 4: Deploy via Tailscale (REQUIRES SETUP)
Add Tailscale GitHub Action step before SSH:
```yaml
- name: Connect to Tailscale
  uses: tailscale/github-action@v4
  with:
    oauth-client-id: ${{ secrets.TS_OAUTH_CLIENT_ID }}
    oauth-secret: ${{ secrets.TS_OAUTH_SECRET }}
    tags: tag:ci
```
**Prerequisite:** Create OAuth client in Tailscale admin console with `tag:ci` tag, add ACL allowing `tag:ci` to access Mac Mini on port 22, store credentials as GitHub secrets.

### Fix 5: Pip caching — NO CHANGE NEEDED
The `setup-python` action with `cache: 'pip'` is already configured and working.

### Fix 6: Swift build validation — DEFER
Requires self-hosted macOS runner. Current local pre-push hook (`scripts/pre-push.sh`) covers this for main branch pushes. Can revisit when the M5 Ultra Mac Studio arrives (more headroom for CI workloads).

## Final Critiques

- **Skeptic:** "Won't re-compiling for 3.11 break the local 3.9 environment?"
  - Response: Yes, potentially. But CLAUDE.md specifies `>=3.11,<3.13` as the target. The local machine running 3.9.6 is the anomaly. The lockfile should match CI. If local install breaks, use `pyenv` or `brew install python@3.12` to get a compatible version. Cross-version pip-compile with `--python-version 3.11` handles markers correctly for the CI target.

- **Pragmatist:** "Is fixing all six issues worth a sprint?"
  - Response: Fixes 1-3 are 15 minutes of config changes. Fix 4 requires Tailscale admin console access (~30 min setup). Fix 5 is already done. Fix 6 is explicitly deferred. Total effort: ~1 hour for fixes 1-3, plus 30 min for fix 4 if Tailscale access is available. This is not a sprint — it's a quick win session.

- **Long-Term Thinker:** "What happens in 6 months?"
  - Response: The Tailscale OAuth approach is stable and well-maintained. The pip-compile workflow is sustainable. The real risk is Python version drift — when the M5 Ultra arrives and the project upgrades to Python 3.13+, the lockfile will need re-compilation. But that's a known, scheduled event. The `--python-version` flag in pip-compile makes this a one-command operation.

## Open Questions

1. **Local Python version:** Is Andrew ready to upgrade from 3.9 to 3.11+? If not, should we use the "pin pytest-asyncio <1.0" approach instead of re-compiling for 3.11?
2. **Tailscale OAuth:** Does Andrew have Tailscale admin console access to create an OAuth client? If not, fix 4 needs to wait.
3. **Test audit on Linux:** Before removing `continue-on-error`, should we do a dry run to see which tests actually fail on ubuntu-latest? (Can be done by temporarily adding `|| true` to capture exit code and log failures.)
4. **Self-hosted runner appetite:** Is running a GitHub Actions runner on the Mac Mini desirable, or does the security/maintenance burden outweigh the benefit of Swift CI?

## Implementation Checklist

- [ ] Re-compile `requirements.txt` with `--python-version 3.11`
- [ ] Update `requirements.in` comment header to reflect 3.11 target
- [ ] Remove `continue-on-error: true` from ci.yml test step
- [ ] Add `-m "not integration"` to CI pytest invocation
- [ ] Fix Claude action permissions (pull-requests: write, issues: write)
- [ ] (Weekend 2026-03-22) Tailscale OAuth: create OAuth client in admin console, add `TS_OAUTH_CLIENT_ID` + `TS_OAUTH_SECRET` GitHub secrets, add `tag:ci` ACL rule, uncomment Tailscale step in deploy.yml
- [ ] (Deferred) Self-hosted macOS runner for Swift builds
