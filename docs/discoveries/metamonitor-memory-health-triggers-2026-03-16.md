# Discovery Report: MetaMonitor + Memory Health + Trigger Metrics (Sprint 15)

**Date:** 2026-03-16
**Confidence:** High
**Decision:** Build Sprint 15 as three loosely-coupled workstreams sharing a common `hestia/learning/` module, with MetaMonitor running hourly on schedule (not real-time), memory health as read-only diagnostic queries, and trigger metrics as a thin threshold-check layer over existing data.

## Hypothesis

Sprint 15 is Hestia's first self-awareness infrastructure. The question: **How should Hestia monitor its own performance, memory health, and system metrics — given M1 16GB constraints, single-user scale, and the need to produce actionable signal (not noise) from day one?**

Sub-questions:
1. What data sources already exist and what gaps need closing?
2. What's the right cadence — real-time, hourly, daily?
3. How do we avoid the MetaMonitor becoming a CPU tax that degrades the thing it's monitoring?
4. What's the minimum viable MetaMonitor that produces genuinely useful insight?

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** OutcomeTracker already records every chat response with implicit signals (quick_followup/accepted/long_gap). Routing audit DB captures every orchestrator decision with confidence + fallback status. ChromaDB exposes `count()` and similarity scores. Research DB has entities, facts, communities. Orders/APScheduler provides scheduling infrastructure. All data is in SQLite (queryable). 988 imported Claude history chunks provide initial corpus. | **Weaknesses:** OutcomeTracker has no chunk attribution — we don't know which memory chunks contributed to a response. No cross-system correlation yet (outcomes vs. routing vs. memory). handler.py is 2510 lines — adding more hooks is risky. M1 16GB leaves minimal headroom for background analysis. OutcomeTracker may not have enough volume yet (deployed Sprint 10, ~2 weeks of data at best). |
| **External** | **Opportunities:** MetaMonitor creates the foundation for ALL downstream learning (Sprints 16-20). Retrieval feedback loop (chunk attribution) is the highest-ROI single addition — enables memory lifecycle decisions in Sprint 16. Industry moving toward RAG evaluation (Precision@k, MRR, chunk attribution) — well-understood patterns. Trigger metrics system turns the research brief from static document into active automation. | **Threats:** Cold-start problem — MetaMonitor may report "insufficient data" for weeks before producing useful patterns. Over-monitoring risk — if MetaMonitor produces noise, Andrew ignores it and it becomes dead infrastructure. CPU budget on M1 — hourly analysis competes with inference. Confusion loop detection has high false-positive risk (multi-turn conversations are normal, not confusion). |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Retrieval feedback loop (chunk IDs in outcome metadata). MetaMonitor hourly analysis with routing quality correlation. Memory health metrics (chunk count, redundancy, staleness). | Correction classification (timezone/factual/preference/tool_usage keyword matching). |
| **Low Priority** | Trigger metrics infrastructure (threshold monitoring for research brief). Knowledge gap detector (curiosity questions in briefing). | Confidence calibrator per-domain tracking (needs more data volume first). Pattern drift detection (insufficient baseline data). |

## Argue (Best Case)

**Sprint 15 closes the most critical gap in Hestia's architecture: the absence of self-awareness.**

The evidence is strong:

1. **Data infrastructure is ready.** OutcomeTracker (Sprint 10) records every response with implicit signals. Routing audit DB (Sprint 14) captures every orchestrator decision. The data exists — it just isn't being analyzed.

2. **Retrieval feedback loop is the single highest-ROI addition.** Currently, when `PromptBuilder` includes memory chunks in context, those chunk IDs are lost — we have no way to correlate "these chunks were used" with "this response got positive/negative feedback." Adding chunk attribution to outcome metadata is a small change (~20 lines in handler.py) that unlocks the entire memory lifecycle (Sprint 16).

3. **Routing quality analysis produces immediate value.** With `agent_route` and `route_confidence` already on outcome records and routing audit entries, we can answer: "Do ARTEMIS-routed responses get better implicit signals than HESTIA_SOLO?" This directly informs whether to adjust confidence thresholds.

4. **Industry validation.** RAG evaluation is a mature field. Precision@k, chunk attribution, and retrieval quality feedback loops are standard practice in production systems (FutureAGI, Morphik, Toloka all document these patterns). We're not inventing — we're implementing proven patterns.

5. **MetaMonitor as hourly batch is low-risk.** Running analysis hourly (not real-time) on SQLite data costs ~100ms of CPU per cycle. No inference calls needed for MetaMonitor itself — it's pure SQL aggregation + threshold checking.

6. **Trigger metrics infrastructure is thin and high-leverage.** A daily cron job checking 8-10 metrics against thresholds in a YAML file, injecting notes into briefings — this is ~200 lines of code that turns the entire research brief into an active monitoring system.

## Refute (Devil's Advocate)

**Sprint 15 risks building monitoring infrastructure before there's enough data to monitor.**

Counter-arguments:

1. **Cold-start problem is real.** OutcomeTracker has been deployed for ~2 weeks. At Andrew's usage rate (~6hr/week), there may be 50-100 outcome records. MetaMonitor needs volume to detect patterns — 50 data points across mixed domains may produce noise, not signal.

   *Mitigation:* Design MetaMonitor to report confidence alongside findings. "Routing quality: ARTEMIS responses 87% positive (n=8, low confidence)" is honest and still useful. Set minimum sample sizes before generating recommendations.

2. **Confusion loop detection is a false-positive magnet.** The original Sprint 11B plan flags ">3 back-and-forth messages on same topic" as a confusion loop. But many legitimate conversations involve 5+ turns on a single topic (debugging, planning, exploration). The detection heuristic needs to be much more nuanced than turn count.

   *Mitigation:* Confusion loops should require BOTH high turn count AND negative implicit signals (quick_followup). A 7-turn conversation where each response gets "accepted" or "long_gap" is engagement, not confusion.

3. **Memory health metrics may reveal problems we can't fix yet.** If ChromaDB health shows 40% redundancy, Sprint 15 can only report it — Sprint 16 (consolidation) is needed to fix it. This could feel like diagnostics without remediation.

   *Mitigation:* Frame memory health as "baseline measurement." You can't improve what you don't measure. Sprint 16 needs these baselines to demonstrate improvement.

4. **handler.py is already 2510 lines.** Adding chunk attribution tracking adds more code to an already overloaded file.

   *Mitigation:* Chunk attribution should be a 1-line metadata addition in the existing `track_response()` call — not new handler logic. The chunk IDs are already available in the `_build_prompt()` pipeline; they just need to be threaded through.

5. **Trigger metrics could become alert fatigue.** If thresholds are poorly calibrated, Andrew gets daily briefing notes about metrics that aren't actionable.

   *Mitigation:* Start with very few triggers (3-4 high-confidence thresholds). Default to "don't alert" — only alert when a metric crosses a threshold for the first time. Suppress repeat alerts for 30 days.

## Third-Party Evidence

### RAG Evaluation Best Practices (2025-2026)

The RAG evaluation field has converged on a standard feedback loop:

1. **Log retrieval telemetry** — query, chunk IDs retrieved, similarity scores, final response
2. **Correlate with outcomes** — user satisfaction, follow-up corrections, task completion
3. **Analyze weekly** — identify degradation, emerging patterns, optimization opportunities
4. **Retrain/adjust** — update embeddings, ranking, chunking based on insights

Sources: [FutureAGI RAG Evaluation Metrics](https://futureagi.com/blogs/rag-evaluation-metrics-2025), [Morphik RAG Strategies](https://www.morphik.ai/blog/retrieval-augmented-generation-strategies), [Toloka RAG Evaluation Guide](https://toloka.ai/blog/rag-evaluation-a-technical-guide-to-measuring-retrieval-augmented-generation/)

### Metacognitive Monitoring Architectures

The literature distinguishes between:

- **Representation-based metacognition** — using internal model states (logits, attention) to assess confidence. Works well for in-distribution tasks, degrades on edge cases.
- **Experience-based metacognition** — using outcome history to calibrate future confidence. More robust but needs data volume.

Hestia should use experience-based metacognition (outcome history) rather than trying to introspect Ollama's internal states. This aligns with the EvolveR framework validated on Qwen 2.5 models.

Sources: [Evidence for Limited Metacognition in LLMs](https://arxiv.org/html/2509.21545v1), [Metacognitive Capabilities in LLMs](https://www.emergentmind.com/topics/metacognitive-capabilities-in-llms)

### AI Agent Observability (2025-2026)

Production agent monitoring platforms (LangSmith, Langfuse, Maxim) track:

- Latency per component (retrieval, inference, tool execution)
- Token usage and cost
- Error rates with root cause classification
- User feedback correlation with system metrics

Key insight: these platforms separate **system observability** (latency, errors, resource usage) from **behavioral observability** (was the response good?). Hestia should do the same — system metrics in trigger infrastructure, behavioral metrics in MetaMonitor.

Sources: [OpenTelemetry AI Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/), [UptimeRobot AI Agent Monitoring](https://uptimerobot.com/knowledge-hub/monitoring/ai-agent-monitoring-best-practices-tools-and-metrics/)

### Alternative Approach Considered: Real-Time Metacognitive Layer

The MIDCA and MetaRAG architectures propose real-time metacognitive monitoring as an inline process. This was explicitly rejected for Hestia because:

1. M1 16GB can't afford a second inference call per request for metacognitive assessment
2. Single-user scale means batch analysis (hourly/daily) produces equivalent insight at 1/100th the cost
3. Real-time monitoring is valuable when you need immediate course correction mid-conversation — Hestia's conversations are short enough that post-hoc analysis is sufficient

## Recommendation

### Architecture: Three workstreams in `hestia/learning/` module

**Audit conditions applied:**
- API namespace: `/v1/learning/` (route module: `hestia/api/routes/learning.py`)
- All `learning.db` tables include `user_id` column from day one
- `LEARNING` added to `LogComponent` enum before any code
- Correction classifier stores type labels only, not raw message content
- `auto-test.sh` mapping: `hestia/learning/` → `tests/test_learning*.py`
- Report self-cleanup: MetaMonitor cleans old reports during each hourly run
- Minimum sample size gates (n ≥ 20) on all analyses

```
hestia/learning/
├── __init__.py
├── models.py              # MetaMonitorReport, MemoryHealthReport, TriggerAlert, etc.
├── database.py            # SQLite: monitor_reports, health_snapshots, trigger_log (all user_id-scoped)
├── meta_monitor.py        # MetaMonitor manager — hourly analysis
├── memory_health.py       # MemoryHealthMonitor — cross-system diagnostics
├── trigger_monitor.py     # TriggerMonitor — threshold checking
├── outcome_pipeline.py    # Outcome → Principle batch pipeline
└── correction_classifier.py  # Keyword-based correction type detection
```

### WS1: MetaMonitor (Core)

**What it does:** Hourly background analysis of outcomes + routing data.

**Key analyses:**
- **Routing quality correlation** — Compare implicit signal distribution (positive/negative) across agent routes (HESTIA_SOLO vs. ARTEMIS vs. APOLLO). SQL joins across `outcomes` and `routing_audit` tables.
- **Acceptance trend** — 7-day rolling window of positive vs. negative signal ratio. Detect declining trend (3+ consecutive days of decline).
- **Confusion loop detection** — Sessions with >5 messages AND >50% quick_followup signals. NOT just turn count — requires negative signal evidence.
- **Latency trend** — Average `duration_ms` from outcomes, grouped by day. Detect upward trend.

**What it does NOT do (yet):**
- No per-domain confidence calibration (insufficient data volume — defer to Sprint 16+)
- No real-time monitoring (hourly batch is sufficient at single-user scale)
- No LLM-powered reflection (pure SQL aggregation — no inference calls)

**Scheduling:** APScheduler job via Orders, runs every 60 minutes. Reports stored in `learning.db`.

**API:** `GET /v1/monitor/report` (latest report), `GET /v1/monitor/routing-quality` (route comparison stats)

**Estimated tests:** ~25

### WS2: Memory Health Monitor

**What it does:** Daily snapshot of memory system health across ChromaDB + knowledge graph.

**Key metrics:**
- `chunk_count` — Total chunks in ChromaDB
- `chunk_count_by_source` — Breakdown by MemorySource (conversation, claude_import, inbox, etc.)
- `redundancy_estimate` — Sample 100 random chunks, compute pairwise cosine similarity, report % with similarity >0.92 (indicates near-duplicates)
- `never_retrieved_pct` — Chunks with zero retrieval hits (requires adding a `retrieval_count` column to memory SQLite — lightweight migration)
- `entity_count`, `fact_count`, `stale_entity_count` (no new facts in 30 days)
- `contradiction_count` — Facts with `status=contradicted`
- `community_count`, `avg_community_size`

**Critical addition: Retrieval Feedback Loop**
- When `PromptBuilder` assembles context, pass chunk IDs into outcome metadata: `metadata={"retrieved_chunk_ids": [id1, id2, ...]}`
- This is the single most important change in Sprint 15 — it enables Sprint 16's importance scoring by letting us correlate "which chunks appear in positive vs. negative outcomes"
- Implementation: ~20 lines in handler.py pipeline (chunk IDs are already available from `memory_manager.search()`)

**Scheduling:** Daily via APScheduler. Snapshots stored in `learning.db`.

**API:** `GET /v1/monitor/memory-health` (latest snapshot), `GET /v1/monitor/memory-health/history?days=30`

**Estimated tests:** ~20

### WS3: Trigger Metrics Infrastructure

**What it does:** Daily check of system metrics against configurable thresholds. When a threshold is crossed, inject a note into the proactive briefing.

**Config:** `config/triggers.yaml`
```yaml
triggers:
  enabled: true
  check_interval_hours: 24

  thresholds:
    memory_total_chunks:
      value: 5000
      direction: above  # alert when above
      message: "Memory chunk count exceeded 5,000. Consider Sprint 16 consolidation."
      cooldown_days: 30

    memory_redundancy_pct:
      value: 30
      direction: above
      message: "Memory redundancy rate is {value}%. Consolidation would reduce noise."
      cooldown_days: 30

    knowledge_entity_count:
      value: 500
      direction: above
      message: "Knowledge graph has {value} entities. Graph RAG Lite (Sprint 17) may be actionable."
      cooldown_days: 30

    inference_avg_latency_ms:
      value: 3000
      direction: above
      message: "Average inference latency is {value}ms. Consider model optimization."
      cooldown_days: 7
```

**Metrics endpoint:** `GET /v1/system/metrics` returns current values for all tracked metrics. Lightweight — all data from existing managers (no new computation).

**Integration:** Trigger alerts stored in `learning.db`. BriefingGenerator queries for unacknowledged alerts and includes them in the daily briefing.

**Estimated tests:** ~10

### Additional Items (from old Sprint 11B)

**Outcome → Principle Pipeline:** Daily batch that queries negative outcomes + quick_followup signals from the last 24 hours, groups by correction type, and feeds into `PrincipleStore.distill_principles()` when 3+ corrections cluster in the same domain. All correction-derived principles start as `status=pending`. Uses existing PrincipleStore infrastructure. ~8 tests.

**Correction Classification:** Enhance `detect_implicit_signal()` to set `metadata["correction_type"]` via keyword matching on the follow-up message content. Four types: timezone, factual, preference, tool_usage. ~4 tests.

**Read-Only Settings Tools:** Register `get_user_settings`, `get_system_status`, `get_user_timezone` as tools in the ToolRegistry. Hestia can introspect her own config for diagnostic responses. ~3 tests.

### Total Estimated Tests: ~70

### Implementation Order

0. **handler.py decomposition** (prerequisite — extract agentic handler + orchestrator calls)
1. **Retrieval feedback loop** (chunk attribution in outcome metadata) — highest ROI, unblocks Sprint 16
2. **Memory health metrics** (read-only diagnostics, baseline measurement)
3. **MetaMonitor core** (routing quality + acceptance trend + confusion detection)
4. **Trigger metrics infrastructure** (config + daily check + briefing integration)
5. **Outcome → Principle pipeline** (connects outcomes to knowledge)
6. **Correction classification + settings tools** (small additions)

### Prerequisites (Chunk 0 — before Sprint 15 proper)

**handler.py decomposition:** Extract at minimum:
- `handle_agentic()` + agentic helpers → `hestia/orchestration/agentic_handler.py`
- `_try_orchestrated_response()` + `_get_orchestrator_config()` → already in `hestia/orchestration/` modules, just need handler.py to call them cleanly

This reduces handler.py from ~2,510 to ~2,100 lines and makes the chunk attribution addition in WS2 safer.

### What Would Change This Recommendation

- **If M1 memory pressure is too high:** Reduce MetaMonitor from hourly to every 4 hours. Memory health from daily to weekly.
- **If OutcomeTracker data volume is too low:** Add a minimum sample size gate (n >= 20 per analysis window) and defer MetaMonitor activation until threshold is met.

## Final Critiques

- **Skeptic:** "MetaMonitor running hourly on M1 with 50 data points will produce meaningless statistics. You're building infrastructure for data you don't have." **Response:** The infrastructure cost is near-zero (SQL aggregation, no inference). The retrieval feedback loop starts collecting chunk attribution immediately — by the time Sprint 16 arrives, we'll have months of data. Building the pipe before the water flows is correct sequencing. The alternative (building Sprint 16 without Sprint 15's feedback data) means flying blind on which chunks to consolidate.

- **Pragmatist:** "Is 70 tests and a new module worth it for hourly reports nobody reads?" **Response:** MetaMonitor reports aren't for Andrew to read manually — they feed downstream systems. Routing quality data adjusts orchestrator thresholds. Memory health baselines prove Sprint 16's consolidation actually improved things. Trigger alerts surface in the daily briefing Andrew already reads. The value is systemic, not in the reports themselves.

- **Long-Term Thinker:** "In 6 months, will this MetaMonitor still be running hourly doing SQL aggregation, or will it have evolved into something more sophisticated?" **Response:** Sprint 19 (Active Inference) replaces MetaMonitor's heuristic thresholds with mathematical prediction error tracking. MetaMonitor is intentionally simple — it's a scaffold that proves the concept before investing in the theory. The data it collects (outcome-chunk correlations, routing quality, memory health baselines) becomes training data for the World Model. MetaMonitor isn't the end state — it's the data collection phase that makes the end state possible.

## Decisions (Resolved)

1. **Chunk attribution granularity:** Log ALL chunk IDs retrieved by memory search, not just top-K. Storage is cheap, and knowing which chunks were retrieved but filtered out is valuable for Sprint 16's importance scoring.

2. **MetaMonitor report retention:** Keep hourly reports for 7 days, then consolidate to daily summaries retained for 90 days.

3. **Briefing integration:** Dedicated "System Alerts" section at the bottom of the briefing. Keeps system metrics separate from personal content.

4. **handler.py decomposition:** Extract `handle_agentic()` and `_try_orchestrated_response()` into separate modules BEFORE Sprint 15 implementation. This is a prerequisite task (Chunk 0), not a post-sprint cleanup. Reduces risk when adding chunk attribution hooks to a 2,510-line file.

## Data Flow Diagram

```
                    ┌─────────────────────────────────────┐
                    │         Chat Pipeline                 │
                    │                                       │
                    │  User Msg → Memory Search → Prompt    │
                    │  → Inference → Response → Track       │
                    │         │                    │        │
                    │    chunk_ids            outcome +     │
                    │         │           chunk_ids in      │
                    │         │             metadata        │
                    └─────────┼──────────────┼─────────────┘
                              │              │
                              ▼              ▼
                    ┌──────────────┐  ┌──────────────┐
                    │  ChromaDB    │  │  outcomes.db  │
                    │  (vectors)   │  │  (signals)    │
                    └──────┬───────┘  └──────┬───────┘
                           │                 │
                    ┌──────▼─────────────────▼───────┐
                    │        MetaMonitor (hourly)      │
                    │                                   │
                    │  • Routing quality analysis        │
                    │  • Acceptance trend                │
                    │  • Confusion loop detection        │
                    │  • Chunk-outcome correlation       │
                    └──────────────┬────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
              ▼                    ▼                     ▼
    ┌──────────────┐    ┌──────────────┐     ┌──────────────┐
    │  learning.db │    │  Briefing     │     │  Config      │
    │  (reports)   │    │  Integration  │     │  Adjustment  │
    └──────────────┘    └──────────────┘     └──────────────┘

    ┌─────────────────────────────────────────────────────┐
    │           Memory Health Monitor (daily)               │
    │                                                       │
    │  ChromaDB count + redundancy → research.db stats →   │
    │  health snapshot → learning.db                        │
    └──────────────────────────────────┬────────────────────┘
                                       │
                                       ▼
    ┌─────────────────────────────────────────────────────┐
    │           Trigger Monitor (daily)                     │
    │                                                       │
    │  config/triggers.yaml thresholds ↔ current metrics   │
    │  → alerts → briefing injection                        │
    └─────────────────────────────────────────────────────┘
```

## Effort Estimate

| Workstream | Days | Tests | Risk |
|------------|------|-------|------|
| WS1: MetaMonitor | 5 | ~25 | Medium (confusion loop false positives) |
| WS2: Memory Health | 3 | ~20 | Low (read-only diagnostics) |
| WS3: Trigger Metrics | 2 | ~10 | Low (thin config layer) |
| Outcome Pipeline | 2 | ~8 | Low (connects existing systems) |
| Correction + Settings | 1 | ~7 | Low (keyword matching + tool registration) |
| **Total** | **~13** | **~70** | |

Includes Chunk 0 (handler.py decomposition, ~1 day). Push forward regardless of calendar estimate.

---

## Sources

- [FutureAGI RAG Evaluation Metrics 2025](https://futureagi.com/blogs/rag-evaluation-metrics-2025)
- [Morphik RAG Strategies](https://www.morphik.ai/blog/retrieval-augmented-generation-strategies)
- [Toloka RAG Evaluation Guide](https://toloka.ai/blog/rag-evaluation-a-technical-guide-to-measuring-retrieval-augmented-generation/)
- [OpenTelemetry AI Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/)
- [UptimeRobot AI Agent Monitoring](https://uptimerobot.com/knowledge-hub/monitoring/ai-agent-monitoring-best-practices-tools-and-metrics/)
- [Evidence for Limited Metacognition in LLMs](https://arxiv.org/html/2509.21545v1)
- [Metacognitive Capabilities in LLMs](https://www.emergentmind.com/topics/metacognitive-capabilities-in-llms)
- [EvolveR: Self-Evolving LLM Agents](https://arxiv.org/abs/2510.16079) — validated on Qwen 2.5
- [MIDCA Architecture](https://ojs.aaai.org/index.php/AAAI/article/view/9886) — AAAI
- [Agentic Metacognition](https://arxiv.org/abs/2509.19783)
- Hestia internal: `docs/discoveries/neural-net-learning-cycle-research.md`
- Hestia internal: `docs/plans/sprint-11-command-center-plan.md`
- Hestia internal: `docs/plans/sprint-7-14-master-roadmap.md`
