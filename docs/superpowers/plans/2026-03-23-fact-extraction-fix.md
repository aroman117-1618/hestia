# Fact Extraction Pipeline Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the fact extraction pipeline so it actually calls the LLM and populates the knowledge graph with entities and facts.

**Architecture:** The root cause is that `fact_extractor.py` calls `client.generate()` — a method that doesn't exist on `InferenceClient` (only `complete()` exists). All 5 call sites silently catch the `AttributeError`. Secondary fix: expose `force_tier` on `complete()` so extraction stays on PRIMARY tier regardless of prompt token count.

**Tech Stack:** Python/FastAPI, Ollama inference client, pytest

**Second opinion:** `docs/plans/fact-extraction-fix-second-opinion-2026-03-23.md`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `hestia/inference/client.py` | Modify | Add `force_tier` + `format` params to `complete()` and `_call_with_routing()` |
| `hestia/inference/router.py` | Read only | Already has `force_tier` on `route()` — no change needed |
| `hestia/research/fact_extractor.py` | Modify | Fix 5x `generate()` → `complete()`, add `think=False` + `force_tier` |
| `hestia/research/manager.py` | Modify | Reduce chunk limit 50 → 15 |
| `tests/test_fact_extraction_debug.py` | Modify | Fix mocks: `generate` → `complete` |
| `tests/test_research_facts.py` | Modify | Fix mocks: `generate` → `complete` |

---

### Task 1: Add `force_tier` and `format` to `complete()` and `_call_with_routing()`

**Files:**
- Modify: `hestia/inference/client.py:431-481` (`_call_with_routing`)
- Modify: `hestia/inference/client.py:940-993` (`complete`)
- Modify: `hestia/inference/client.py:340-370` (`_call_ollama`)

- [ ] **Step 1: Add `force_tier` param to `_call_with_routing()`**

Add `force_tier: Optional[str] = None` parameter. Pass it to `self.router.route()` as `force_tier=ModelTier(force_tier) if force_tier else None`.

- [ ] **Step 2: Add `format` param to `_call_with_routing()`**

Add `format: Optional[str] = None` parameter. Pass it through to `_call_ollama()` / `_call_local_with_retries()`.

- [ ] **Step 3: Add `format` param to `_call_ollama()`**

Add `format: Optional[str] = None` parameter. If set, add `request_data["format"] = format` to the request body.

- [ ] **Step 4: Add `force_tier` and `format` params to `complete()`**

Add both params to `complete()` signature. Pass through to `_call_with_routing()`.

- [ ] **Step 5: Run existing inference tests**

Run: `python -m pytest tests/test_inference*.py -v --timeout=30`
Expected: All pass (new params are optional with defaults)

- [ ] **Step 6: Commit**

```bash
git add hestia/inference/client.py
git commit -m "feat(inference): expose force_tier and format params on complete()"
```

---

### Task 2: Fix all 5 `generate()` → `complete()` call sites in fact_extractor.py

**Files:**
- Modify: `hestia/research/fact_extractor.py` (lines 167, 198, 223, 253, 384)

- [ ] **Step 1: Fix Phase 3 call (line 167)**

`client.generate(prompt=..., system=..., format="json")` → `client.complete(prompt=..., system=..., think=False, force_tier="primary", format="json")`

- [ ] **Step 2: Fix Phase 1 call (line 198)**

Same pattern: `generate` → `complete`, add `think=False, force_tier="primary"`

- [ ] **Step 3: Fix Phase 2 call (line 223)**

Same pattern.

- [ ] **Step 4: Fix legacy fallback call (line 253)**

Same pattern.

- [ ] **Step 5: Fix contradiction checker call (line 384)**

Same pattern.

- [ ] **Step 6: Commit**

```bash
git add hestia/research/fact_extractor.py
git commit -m "fix(research): generate() → complete() — 5 call sites, add think=False + force_tier"
```

---

### Task 3: Fix test mocks from `generate` to `complete`

**Files:**
- Modify: `tests/test_fact_extraction_debug.py` (lines 43, 55-56, 83, 96, 112)
- Modify: `tests/test_research_facts.py` (lines 882, 974, 1006)

- [ ] **Step 1: Fix `test_fact_extraction_debug.py`**

Replace all `mock_client.generate` with `mock_client.complete` (6 occurrences).

- [ ] **Step 2: Fix `test_research_facts.py`**

Replace all `mock_inference.generate` with `mock_inference.complete` (3 occurrences).

- [ ] **Step 3: Run the fixed tests**

Run: `python -m pytest tests/test_fact_extraction_debug.py tests/test_research_facts.py -v --timeout=30`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_fact_extraction_debug.py tests/test_research_facts.py
git commit -m "fix(tests): update fact extraction mocks generate → complete"
```

---

### Task 4: Reduce manager chunk limit from 50 to 15

**Files:**
- Modify: `hestia/research/manager.py:224`

- [ ] **Step 1: Change limit**

In `extract_facts()`, change `results = await memory_mgr.search(query="*", limit=50, ...)` → `limit=15`.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All 2644 pass

- [ ] **Step 3: Commit**

```bash
git add hestia/research/manager.py
git commit -m "fix(research): reduce extraction chunk limit 50 → 15 for M1 performance"
```
