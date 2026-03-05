# Sprint 11A: Dual Local Model Architecture — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Swap primary model from Qwen 2.5 7B to Qwen 3.5 9B, add Qwen 2.5 Coder 7B as coding specialist with pattern-based routing, expand CLI context budget, and document hardware upgrade path.

**Architecture:** The router gains a 4th tier (CODING) alongside PRIMARY/COMPLEX/CLOUD. Coding keyword patterns (already defined in `routing.complex_patterns`) route to the coding model when enabled. The council SLM is unchanged. Ollama hot-swaps models on Apple Silicon — only one active in GPU memory at a time.

**Tech Stack:** Python 3.12, FastAPI, Ollama, YAML config, pytest

**Design Doc:** `docs/plans/2026-03-05-model-swap-planning-design.md`

---

## Task 1: Add CODING Tier to Router

**Files:**
- Modify: `hestia/inference/router.py:27-31` (ModelTier enum)
- Modify: `hestia/inference/router.py:129-183` (_load_config)
- Modify: `hestia/inference/router.py:188-276` (route method)
- Modify: `hestia/inference/router.py:292-298` (_get_config_for_tier)
- Modify: `hestia/inference/router.py:300-307` (_get_fallback_tier)
- Test: `tests/test_inference.py`

**Step 1: Write failing tests for coding tier routing**

Add to `tests/test_inference.py`:

```python
def test_coding_tier_routes_code_patterns():
    """Coding model is selected for code-related prompts when enabled."""
    router = ModelRouter()
    # Coding model is enabled via config
    assert router.coding_model is not None
    assert router.coding_model.enabled is True

    decision = router.route("write code for a REST endpoint")
    assert decision.tier == ModelTier.CODING
    assert decision.model_config.name == "qwen2.5-coder:7b"


def test_coding_tier_fallback_when_disabled():
    """Falls back to primary when coding model is disabled."""
    router = ModelRouter()
    router.coding_model.enabled = False
    decision = router.route("write code for a REST endpoint")
    assert decision.tier == ModelTier.PRIMARY


def test_coding_tier_in_config_for_tier():
    """_get_config_for_tier returns coding model."""
    router = ModelRouter()
    config = router._get_config_for_tier(ModelTier.CODING)
    assert config is not None
    assert config.name == "qwen2.5-coder:7b"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_inference.py::test_coding_tier_routes_code_patterns -v`
Expected: FAIL — `ModelTier` has no `CODING` member

**Step 3: Implement CODING tier in router**

In `hestia/inference/router.py`:

a) Add to `ModelTier` enum (line ~30):
```python
class ModelTier(Enum):
    """Model tiers for routing."""
    PRIMARY = "primary"      # General chat (Qwen 3.5 9B)
    CODING = "coding"        # Code specialist (Qwen 2.5 Coder 7B)
    COMPLEX = "complex"      # Large local (reserved for hardware upgrade)
    CLOUD = "cloud"          # Cloud LLM (Anthropic/OpenAI/Google)
```

b) Add coding_model config parsing in `_load_config()` after complex_data block (~line 157):
```python
        # Coding specialist model config
        coding_data = data.get("coding_model", {})
        self.coding_model = ModelConfig(
            name=coding_data.get("name", "qwen2.5-coder:7b"),
            context_limit=coding_data.get("context_limit", 32768),
            max_tokens=coding_data.get("max_tokens", 4096),
            temperature=coding_data.get("temperature", 0.0),
            request_timeout=coding_data.get("request_timeout", 90.0),
            enabled=coding_data.get("enabled", False),
        )
```

c) Update routing logic in `route()` — replace the complex model checks (~lines 247, 263):

In the `enabled_smart` block (after cloud spillover check, ~line 244):
```python
            # Check for coding patterns → route to coding model if enabled
            if self.coding_model.enabled and self._is_complex_request(prompt, token_count):
                return RoutingDecision(
                    tier=ModelTier.CODING,
                    model_config=self.coding_model,
                    reason="coding_request_pattern",
                    fallback_tier=fallback,
                )

            # Check for complex patterns → route to complex model if enabled
            if self.complex_model.enabled and self._is_complex_request(prompt, token_count):
                return RoutingDecision(
                    tier=ModelTier.COMPLEX,
                    model_config=self.complex_model,
                    reason="complex_request_pattern",
                    fallback_tier=fallback,
                )
```

In the `disabled` block (~line 262):
```python
        # disabled: local-only routing
        if self.coding_model.enabled and self._is_complex_request(prompt, token_count):
            return RoutingDecision(
                tier=ModelTier.CODING,
                model_config=self.coding_model,
                reason="coding_request_pattern",
                fallback_tier=ModelTier.PRIMARY,
            )

        if self.complex_model.enabled and self._is_complex_request(prompt, token_count):
            return RoutingDecision(
                tier=ModelTier.COMPLEX,
                model_config=self.complex_model,
                reason="complex_request_pattern",
                fallback_tier=ModelTier.PRIMARY,
            )
```

d) Update `_get_config_for_tier()`:
```python
    def _get_config_for_tier(self, tier: ModelTier) -> Optional[ModelConfig]:
        """Get model config for a tier."""
        return {
            ModelTier.PRIMARY: self.primary_model,
            ModelTier.CODING: self.coding_model,
            ModelTier.COMPLEX: self.complex_model,
            ModelTier.CLOUD: self.cloud_model,
        }.get(tier)
```

e) Update `_get_fallback_tier()` — CODING falls back to PRIMARY:
```python
        if tier == ModelTier.CODING:
            return ModelTier.PRIMARY
```

f) Update `get_status()` to include coding model info (similar to primary/complex blocks).

g) Update `__init__` failure counts and last_success dicts to include `ModelTier.CODING`.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_inference.py -v --timeout=30`
Expected: All pass including 3 new tests

**Step 5: Commit**

```bash
git add hestia/inference/router.py tests/test_inference.py
git commit -m "feat: add CODING model tier to router for code-specialist routing"
```

---

## Task 2: Update inference.yaml Config

**Files:**
- Modify: `hestia/config/inference.yaml`

**Step 1: Update primary model and add coding model config**

In `hestia/config/inference.yaml`:

a) Update primary_model block (~line 24):
```yaml
primary_model:
  name: "qwen3.5:9b"
  context_limit: 32768
  max_tokens: 2048
  temperature: 0.0
  request_timeout: 90.0
```

b) Add coding_model block after complex_model (~line 47):
```yaml
# CODING: Code specialist for programming tasks
# - Best-in-class code generation at 7B scale (88.4% HumanEval)
# - Activated by routing.complex_patterns keyword matching
# - Falls back to primary_model when disabled
coding_model:
  name: "qwen2.5-coder:7b"
  context_limit: 32768
  max_tokens: 4096
  temperature: 0.0
  request_timeout: 90.0
  enabled: true
```

c) Update `model_name` default (~line 53):
```yaml
model_name: "qwen3.5:9b"
```

d) Add coding-specific patterns to `routing.complex_patterns` (~line 58):
```yaml
routing:
  complex_patterns:
    - "analyze"
    - "explain in detail"
    - "step by step"
    - "write code"
    - "debug"
    - "review"
    - "refactor"
    - "implement"
    - "fix.*bug"
    - "test.*for"
    - "function.*that"
    - "class.*that"
    - "write.*script"
    - "code.*review"
    - "pull request"
  complex_token_threshold: 500
```

**Step 2: Run existing tests to verify config doesn't break anything**

Run: `python -m pytest tests/test_inference.py -v --timeout=30`
Expected: All pass (router reads from config, new fields have defaults)

**Step 3: Commit**

```bash
git add hestia/config/inference.yaml
git commit -m "feat: config — qwen3.5:9b primary, qwen2.5-coder:7b coding specialist"
```

---

## Task 3: Update InferenceClient Default

**Files:**
- Modify: `hestia/inference/client.py:72`
- Test: `tests/test_inference.py`

**Step 1: Update default model name**

In `hestia/inference/client.py`, line 72:
```python
    model_name: str = "qwen3.5:9b"  # Default to general chat model
```

**Step 2: Update test assertion for default config**

In `tests/test_inference.py`, update the test at ~line 74-75:
```python
    def test_default_config(self):
        config = InferenceConfig()
        assert config.model_name == "qwen3.5:9b"
```

And the fallback test at ~line 89:
```python
        assert config.model_name == "qwen3.5:9b"
```

**Step 3: Run tests**

Run: `python -m pytest tests/test_inference.py::TestInferenceConfig -v`
Expected: All pass

**Step 4: Commit**

```bash
git add hestia/inference/client.py tests/test_inference.py
git commit -m "feat: update default model to qwen3.5:9b"
```

---

## Task 4: Update Handler for Coding Model Routing

**Files:**
- Modify: `hestia/orchestration/handler.py` (streaming handler, ~line 750)
- Modify: `hestia/inference/client.py` (chat method — pass routing decision through)
- Test: `tests/test_handler_streaming.py`

**Step 1: Write failing test for coding model selection in streaming**

Add to `tests/test_handler_streaming.py`:

```python
@pytest.mark.asyncio
async def test_streaming_uses_coding_model_for_code_requests():
    """Coding requests route to coding model when enabled."""
    handler = RequestHandler()

    # Verify router has coding model enabled
    assert handler.inference_client.router.coding_model.enabled is True

    # Route a coding request
    decision = handler.inference_client.router.route("write code for parsing JSON")
    assert decision.tier == ModelTier.CODING
    assert "coder" in decision.model_config.name
```

**Step 2: Run to verify test passes (or fails if config not loaded)**

Run: `python -m pytest tests/test_handler_streaming.py::test_streaming_uses_coding_model_for_code_requests -v`

**Step 3: Verify the inference client passes model_name override correctly**

Check that `_call_ollama()` in `client.py` already accepts `model_name` parameter. Look at the existing call chain:

In `client.py`, `_call_ollama()` has a `model_name` parameter that overrides the default. The router's `RoutingDecision.model_config.name` is already threaded through `_call_with_routing()` → `_call_ollama(model_name=decision.model_config.name)`.

This means **no handler changes are needed** — the router already handles model selection, and the client already respects the routing decision. The coding model routing is entirely contained in the router (Task 1).

**Step 4: Verify with a broader test run**

Run: `python -m pytest tests/test_handler_streaming.py -v --timeout=30`
Expected: All pass

**Step 5: Commit (if any changes were needed)**

```bash
git add tests/test_handler_streaming.py
git commit -m "test: verify coding model routing in handler streaming path"
```

---

## Task 5: Update Test Fixtures (Model Name References)

**Files:**
- Modify: `tests/test_inference.py` (~10 references)
- Modify: `tests/test_inference_stream.py` (~10 references)
- Modify: `tests/test_handler_streaming.py` (~3 references)
- Modify: `tests/test_investigate.py` (~1 reference)
- Modify: `tests/test_council.py` (~3 SLM references — verify unchanged)
- Modify: `hestia-cli/tests/test_renderer.py` (~2 references)

**Step 1: Bulk update model name in test fixtures**

Search-and-replace `"qwen2.5:7b"` → `"qwen3.5:9b"` in all test files **except** where the test explicitly tests a specific model name (council SLM tests use `"qwen2.5:0.5b"` — leave those alone).

Files and approximate line counts:
- `tests/test_inference.py`: ~12 occurrences
- `tests/test_inference_stream.py`: ~10 occurrences
- `tests/test_handler_streaming.py`: ~2 occurrences
- `tests/test_investigate.py`: ~1 occurrence
- `hestia-cli/tests/test_renderer.py`: ~2 occurrences

**Do NOT change:**
- `tests/test_council.py` references to `"qwen2.5:0.5b"` — those test the SLM, not primary
- Any test that explicitly tests config fallback behavior

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Run: `cd hestia-cli && python -m pytest tests/ -v`
Expected: All 1611 tests pass (1608 passing, 3 skipped)

**Step 3: Commit**

```bash
git add tests/ hestia-cli/tests/
git commit -m "test: update mock model names to qwen3.5:9b"
```

---

## Task 6: Expand CLI Context Budget

**Files:**
- Modify: `hestia-cli/hestia_cli/context.py:17-22`
- Test: `hestia-cli/tests/test_context.py`

**Step 1: Update budget constants**

In `hestia-cli/hestia_cli/context.py`:
```python
# Project files to auto-include, in priority order.
# We stop adding files once we hit the token budget.
PROJECT_FILES: List[str] = [
    "CLAUDE.md",       # Moved to first — most valuable for coding context
    "SPRINT.md",
    "ROADMAP.md",
    "README.md",
]

# Max characters per file and total budget
MAX_CHARS_PER_FILE = 4000   # Was 2000
MAX_TOTAL_CHARS = 16000     # Was 6000
```

**Step 2: Update any tests that assert on old budget values**

Check `hestia-cli/tests/test_context.py` for tests that use the old constants. Update expected truncation behavior if tests reference 2000/6000.

**Step 3: Run CLI tests**

Run: `cd hestia-cli && python -m pytest tests/test_context.py -v`
Expected: All pass

**Step 4: Commit**

```bash
git add hestia-cli/hestia_cli/context.py hestia-cli/tests/test_context.py
git commit -m "feat: expand CLI context budget — CLAUDE.md first, 16K total"
```

---

## Task 7: ADR-040 + Documentation Updates

**Files:**
- Modify: `docs/hestia-decision-log.md` (add ADR-040, update ADR-001 status)
- Modify: `CLAUDE.md` (model table, SLM references, known issues)
- Modify: `docs/reference/deployment.md` (model pull commands)
- Modify: `docs/reference/backend-quickstart.md` (model references)
- Modify: `SPRINT.md` (add Sprint 11A)
- Modify: `docs/plans/sprint-7-14-master-roadmap.md` (insert 11A + 12A)
- Modify: `.claude/projects/-Users-andrewlonati-hestia/memory/MEMORY.md` (model patterns)

**Step 1: Add ADR-040 to decision log**

Append to `docs/hestia-decision-log.md`:

```markdown
### ADR-040: Dual Local Model Architecture

**Date**: 2026-03-05
**Status**: Accepted (Supersedes ADR-001)

#### Context
Qwen 2.5 7B was the original primary model (ADR-001), chosen for 16GB RAM constraint. In March 2026, better models are available at the same RAM tier: Qwen 3.5 9B (general) and Qwen 2.5 Coder 7B (code specialist, 88.4% HumanEval). A dual-model architecture routes coding requests to the specialist while keeping general chat on the newer general model.

#### Decision
1. **Primary model**: `qwen3.5:9b` — general chat, Q&A, daily ops, multimodal (262K native context)
2. **Coding model**: `qwen2.5-coder:7b` — code generation, review, debugging (88.4% HumanEval)
3. **Council SLM**: `qwen2.5:0.5b` — unchanged (intent classification only)
4. **Routing**: Existing `complex_patterns` keyword matching routes coding requests to coding model via new `ModelTier.CODING` tier
5. **Complex model**: Remains disabled, reserved for hardware upgrade

#### Hardware Upgrade Path (M5 Ultra Mac Studio, H2-2026+)
Target: Max RAM (expected 256GB+ unified, ~800 GB/s bandwidth).

**Playbook:**
1. Assess model landscape at time of upgrade (candidates: Qwen3-Coder-480B, GLM-4.7, GLM-5 at 2-bit)
2. Update `inference.yaml`: primary → 32-70B general, coding → best available MoE, enable complex tier
3. Expand context budgets (TOTAL_BUDGET → 131K+, MEMORY_BUDGET → 16K, HISTORY_BUDGET → 80K)
4. Expand CLI context budget (MAX_TOTAL_CHARS → 32K+)
5. Pull new models via Ollama, run full test suite, verify routing
6. Consider MLX backend for 20-30% speed improvement over Ollama on Apple Silicon
7. Update ADR-040 with actual model choices

See `docs/plans/2026-03-05-model-swap-planning-design.md` for full upgrade playbook.

#### Alternatives Considered
- **A: Add 4th tier (CODING)** — Chosen. Clean separation, explicit config block.
- **B: Repurpose COMPLEX tier** — Rejected. Conceptually muddy, complicates hardware upgrade.
- **C: Council intent-driven** — Rejected. IntentType enum lacks coding intents; would require SLM prompt changes.

#### Consequences
- Positive: Better code quality from specialized model (88.4% vs ~60% HumanEval)
- Positive: Better general chat from newer model (Qwen 3.5 > 2.5 on instruction following)
- Positive: No additional RAM (Ollama hot-swaps, one active at a time)
- Positive: Hardware upgrade path documented — config-only changes when M5 Ultra arrives
- Negative: ~1s model swap latency when switching between models on first request
- Negative: Two models on disk (~11GB total vs ~4.5GB)
```

**Step 2: Update ADR-001 status**

Change ADR-001 status from `Accepted (Updated 2025-01-12)` to `Superseded by ADR-040 (2026-03-05)`.

Update the Hardware Upgrade Path section in ADR-001:
```markdown
#### Hardware Upgrade Path
See ADR-040 for current upgrade path. Original Mixtral plan superseded by dual-model architecture.
```

**Step 3: Update CLAUDE.md model table**

In the Technical Stack table:
```
| Model | Qwen 3.5 9B (general) + Qwen 2.5 Coder 7B (coding) via Ollama, local + cloud providers |
| SLM | qwen2.5:0.5b (council intent classification, ~100ms) |
```

Update Known Issues:
```markdown
### Known Issues (Mac Mini)
- Council needs `qwen2.5:0.5b` pulled on Mac Mini
- Coding model needs `qwen2.5-coder:7b` pulled on Mac Mini
- General model needs `qwen3.5:9b` pulled on Mac Mini
- Server must be restarted after code deploys (no hot-reload)
```

**Step 4: Update deployment.md**

```markdown
- Ollama running with `qwen3.5:9b`, `qwen2.5-coder:7b`, and `qwen2.5:0.5b` pulled
```

**Step 5: Update backend-quickstart.md model references**

Replace `qwen2.5:7b` with `qwen3.5:9b` in all examples. Add `qwen2.5-coder:7b` to pull commands.

**Step 6: Update SPRINT.md**

Add Sprint 11A entry at top, move existing Sprint 11 to 11B.

**Step 7: Update master roadmap**

Insert Sprint 11A and 12A placeholder in the sprint table and dependency chain.

**Step 8: Update MEMORY.md**

Update "Backend Patterns" section with new model names and routing behavior.

**Step 9: Commit all docs**

```bash
git add docs/ CLAUDE.md SPRINT.md .claude/
git commit -m "docs: ADR-040 dual local model architecture + hardware upgrade playbook"
```

---

## Task 8: Final Verification

**Step 1: Run full backend test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: 1608+ passing, 3 skipped

**Step 2: Run CLI test suite**

Run: `cd hestia-cli && python -m pytest tests/ -v`
Expected: 66 passing

**Step 3: Verify config loads cleanly**

Run: `python -c "from hestia.inference.router import ModelRouter; r = ModelRouter(); print(f'Primary: {r.primary_model.name}, Coding: {r.coding_model.name}, Coding enabled: {r.coding_model.enabled}')"`
Expected: `Primary: qwen3.5:9b, Coding: qwen2.5-coder:7b, Coding enabled: True`

**Step 4: Verify routing decision**

Run: `python -c "from hestia.inference.router import ModelRouter; r = ModelRouter(); d = r.route('write code for a REST endpoint'); print(f'Tier: {d.tier.value}, Model: {d.model_config.name}, Reason: {d.reason}')"`
Expected: `Tier: coding, Model: qwen2.5-coder:7b, Reason: coding_request_pattern`

**Step 5: Verify non-coding request stays on primary**

Run: `python -c "from hestia.inference.router import ModelRouter; r = ModelRouter(); d = r.route('what is on my calendar tomorrow'); print(f'Tier: {d.tier.value}, Model: {d.model_config.name}')"`
Expected: `Tier: primary, Model: qwen3.5:9b`

**Step 6: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: sprint 11A final adjustments"
```

---

## Deployment (Mac Mini)

After all code is committed and pushed:

```bash
# SSH to Mac Mini
ssh andrewroman117@hestia-3.local

# Pull new models
ollama pull qwen3.5:9b
ollama pull qwen2.5-coder:7b

# Verify models available
ollama list
# Should show: qwen3.5:9b, qwen2.5-coder:7b, qwen2.5:0.5b

# Deploy code (CI/CD or manual)
cd ~/hestia && git pull origin main

# Restart server
lsof -i :8443 | grep LISTEN | awk '{print $2}' | xargs kill -9
source .venv/bin/activate
python -m hestia.api.server &

# Verify health
curl -k https://localhost:8443/v1/health
```

---

## Summary

| Task | Files Changed | Tests | Effort |
|------|--------------|-------|--------|
| 1. CODING tier in router | router.py | 3 new | 45 min |
| 2. inference.yaml config | inference.yaml | existing pass | 15 min |
| 3. Client default | client.py | 2 updated | 10 min |
| 4. Handler verification | test_handler_streaming.py | 1 new | 15 min |
| 5. Test fixture updates | 5 test files | ~25 updated | 20 min |
| 6. CLI context budget | context.py | existing updated | 15 min |
| 7. Documentation | 7 doc files | — | 45 min |
| 8. Final verification | — | full suite | 15 min |
| **Total** | **~15 files** | **~6 new, ~25 updated** | **~3 hrs** |
