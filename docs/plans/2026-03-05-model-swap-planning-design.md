# Design: Dual Local Model Architecture + Planning Capability

**Date:** 2026-03-05
**Status:** Approved
**Sprint:** 11A (Model Swap) + 12A (Planning Capability)

---

## Problem Statement

Hestia's primary model (Qwen 2.5 7B) provides adequate chat quality but underperforms on coding tasks. The CLI has context injection infrastructure (git state, project files) but no structured planning mode. Cloud routing exists but is underutilized for development workflows.

## Decisions

1. **Swap primary model** from `qwen2.5:7b` to `qwen3.5:9b` (better instruction following, multimodal, 262K native context)
2. **Add coding specialist** model `qwen2.5-coder:7b` (88.4% HumanEval, FIM support, code-optimized)
3. **Council SLM unchanged** at `qwen2.5:0.5b` (intent classification only, fast and sufficient)
4. **Council intent drives model selection** — coding intents route to specialist, everything else to primary
5. **Cloud routing for planning** — `/plan` command routes to cloud when available (Sonnet-quality output)
6. **Expand context budget** — CLI project file injection from 6K to 16K chars

## Architecture

### Model Routing Flow

```
User Message
    |
    v
Council SLM (qwen2.5:0.5b, ~100ms)
    |
    v
IntentType + Confidence
    |
    +--[TOOL/REFACTOR/ANALYZE, conf > 0.6]--> coding_model (qwen2.5-coder:7b)
    +--[CHAT/QUERY/CREATIVE]----------------> primary_model (qwen3.5:9b)
    +--[Cloud enabled_full]-----------------> cloud (Claude Sonnet / GPT-4o)
    +--[Cloud enabled_smart + spillover]----> cloud (fallback after local failure)
```

### Model Configuration

| Role | Model | Context | Max Output | RAM (Q4) | Purpose |
|------|-------|---------|------------|----------|---------|
| Primary | `qwen3.5:9b` | 32K (conservative) | 2048 | ~6GB | Chat, Q&A, daily ops, multimodal |
| Coding | `qwen2.5-coder:7b` | 32K | 4096 | ~4.5GB | Code gen, review, debugging |
| Council SLM | `qwen2.5:0.5b` | 2K | 256 | ~0.4GB | Intent classification |
| Complex | *(disabled)* | — | — | — | Reserved for hardware upgrade |

Note: Ollama hot-swaps models on Apple Silicon. Only one model active in GPU memory at a time. Total disk: ~11GB for all three models.

### Intent-to-Model Mapping

| IntentType | Model | Rationale |
|-----------|-------|-----------|
| CHAT | primary | Conversational, personality-driven |
| QUERY | primary | Information retrieval, memory search |
| CREATIVE | primary | Writing, brainstorming |
| TOOL | coding | Tool calls often involve code analysis |
| REFACTOR | coding | Code restructuring |
| ANALYZE | coding | Code review, debugging, architecture |

Confidence threshold: 0.6. Below threshold, defaults to primary (safe fallback).

## Sprint 11A: Model Swap (~4-5 hrs)

### Config Changes
- `inference.yaml`: primary_model name, new coding_model block, expanded routing patterns
- `context.py`: MAX_CHARS_PER_FILE 2000->4000, MAX_TOTAL_CHARS 6000->16000

### Code Changes
- `inference/router.py`: Add `coding_model` ModelConfig parsing, new `ModelTier.CODING` enum value
- `inference/client.py`: Update default model_name fallback
- `orchestration/handler.py`: After council intent (step 6.5), override routing to coding model when intent matches
- Tests: Update ~15 mock model names, add ~6 new routing tests
- Docs: ADR-040, CLAUDE.md, deployment.md, quickstart.md, SPRINT.md, roadmap

### Deployment Steps
```bash
# On Mac Mini (after code deploy)
ollama pull qwen3.5:9b
ollama pull qwen2.5-coder:7b
# Existing models stay: qwen2.5:7b (can remove later), qwen2.5:0.5b (council)
```

## Sprint 12A: Planning Capability (~8-10 hrs, after MetaMonitor gate)

### Scope
- `/plan` CLI command with specialized system prompt
- Cloud-routed planning with 8K output tokens
- Multi-turn tool loop (3 rounds: read -> analyze -> plan)
- `grep_files` + `glob_files` codebase exploration tools
- Plan persistence to `data/plans/`
- Expanded sandbox allowlist for CWD

### Deferred (not in scope)
- Full agent loop with autonomous iteration
- Codebase indexing via ChromaDB embeddings
- Plan execution/scaffolding

## Hardware Upgrade Playbook (M5 Ultra Mac Studio)

**Target hardware:** M5 Ultra Mac Studio, max RAM (expected 256GB+ unified memory, ~800 GB/s bandwidth)

**When the hardware arrives, follow this checklist:**

### Step 1: Model Assessment (Day 1)
Review the open-source model landscape at time of upgrade. As of March 2026, the candidates are:

| Model | Params | Active | RAM (Q4) | Quality |
|-------|--------|--------|----------|---------|
| **Qwen3-Coder-480B** | 480B MoE | 35B | ~120GB | Sonnet-level coding |
| **GLM-4.7** (full) | ~300B MoE | varies | ~135GB | 73.8% SWE-bench |
| **GLM-5** | 744B MoE | 40B | ~241GB (Q2) | 95.8% SWE-bench, frontier-class |
| **Devstral-24B** | 24B dense | 24B | ~14GB | Fast specialist |

At 256GB unified memory, GLM-5 at 2-bit dynamic quant (241GB) becomes viable for the first time on consumer hardware. Evaluate quality vs speed tradeoffs at time of upgrade — the model landscape moves fast.

### Step 2: Config Changes
```yaml
# inference.yaml — suggested starting point (verify against benchmarks at time)
primary_model:
  name: "<best general 32-70B model>"     # e.g. qwen3.5:70b or successor
  context_limit: 131072                    # Larger context with more RAM
  max_tokens: 4096

coding_model:
  name: "<best coding MoE model>"          # e.g. qwen3-coder-480b or GLM-5
  context_limit: 131072
  max_tokens: 8192                         # Full plan-length output
  enabled: true

complex_model:
  name: "<large reasoning model>"          # e.g. deepseek-r1 or successor
  context_limit: 131072
  max_tokens: 8192
  enabled: true                            # Finally enable this tier

council:
  local_slm_model: "<fast 1-3B model>"    # May upgrade from 0.5b
```

### Step 3: Context Budget Expansion
```python
# context.py — expand to match larger context windows
MAX_CHARS_PER_FILE = 8000    # or remove limit entirely
MAX_TOTAL_CHARS = 32000

# prompt.py — expand token budgets
TOTAL_BUDGET = 131072        # Match model context
MEMORY_BUDGET = 16000        # More memory retrieval
HISTORY_BUDGET = 80000       # Much longer conversations
```

### Step 4: Validation
```bash
# Pull new models
ollama pull <model-names>

# Run test suite
python -m pytest tests/ -v --timeout=30

# Smoke test inference
curl -X POST https://localhost:8443/v1/chat \
  -H "X-Hestia-Device-Token: $TOKEN" \
  -d '{"content": "Write a Python function to parse CSV files with error handling"}'

# Benchmark: time a coding request, verify model routing
# Check logs: grep "Executing.*coding_model" logs/hestia.log
```

### Step 5: Performance Tuning
- M5 Ultra at ~800 GB/s bandwidth → expect 20-40 tok/s on 70B models, 5-10 tok/s on 480B MoE
- Enable KV cache quantization (Q8_0) for longer context without RAM pressure
- Consider running MLX backend instead of Ollama for 20-30% speed improvement on Apple Silicon
- If running GLM-5 (241GB Q2), monitor thermal throttling — sustained load may need active cooling

### Step 6: Documentation
- Update ADR-040 with actual model choices
- Update CLAUDE.md model table
- Update deployment docs with new pull commands
- Run `./scripts/count-check.sh` to verify test/endpoint counts

## Roadmap Integration

```
Sprint 10:  Chat Redesign + OutcomeTracker        COMPLETE
Sprint 11A: Model Swap + Coding Specialist         NEW (~4-5 hrs)
Sprint 11B: Command Center + MetaMonitor           Existing (was Sprint 11)
  Gate 2: OutcomeTracker signals + M1 memory profile
Sprint 12:  Health Dashboard & Whoop               Existing
Sprint 12A: Planning Capability (/plan)            NEW (~8-10 hrs)
Sprint 13:  Active Inference Foundation            Existing
Sprint 14:  Anticipatory Execution                 Existing
```

## Related Documents

| Document | Action |
|----------|--------|
| `docs/hestia-decision-log.md` | New ADR-040, supersede ADR-001 |
| `CLAUDE.md` | Update model table, SLM reference, known issues |
| `SPRINT.md` | Add Sprint 11A |
| `docs/plans/sprint-7-14-master-roadmap.md` | Insert 11A + 12A |
| `docs/reference/deployment.md` | Update model pull commands |
| `docs/reference/backend-quickstart.md` | Update model references |
| `.claude/projects/.../memory/MEMORY.md` | Update model patterns |
