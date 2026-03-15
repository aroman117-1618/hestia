# Discovery Report: Hestia Enhancement Candidates Assessment
**Date:** 2026-03-15
**Confidence:** High
**Decision:** Adopt Google Workspace CLI and Bright Data MCP as high-value, low-effort wins. Defer Graphiti pending hardware upgrade. Skip Markowitz/Dynamic Rebalancing (overengineered for current scale). Gitingest and Code Executor are low-priority given existing tooling.

## Hypothesis
Seven candidate enhancements were evaluated for viability and impact on Hestia: (1) Markowitz optimization for resource/model allocation, (2) Dynamic Rebalancing for scheduled task reallocation, (3) Code Executor MCP, (4) Gitingest MCP, (5) Graphiti MCP, (6) Bright Data Web MCP, (7) Google Workspace CLI. The question: which provide meaningful capability uplift relative to integration effort and M1 16GB hardware constraints?

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Mature module architecture (26 modules, manager pattern), existing MCP-compatible tool registry, APScheduler for orders, ChromaDB + SQLite memory, 20 Apple tools, investigate module for URL analysis, 3-state cloud routing already optimized | **Weaknesses:** M1 16GB RAM ceiling, single-model-in-GPU constraint, no Google ecosystem integration (Apple-only), no sandboxed code execution, graph_builder is simple (no temporal awareness, no LLM-powered entity extraction) |
| **External** | **Opportunities:** Google Workspace CLI (gws) is brand new (March 2026), production-quality, with built-in MCP server; Bright Data free tier (5K req/mo) dramatically upgrades investigate module; Graphiti would transform memory into a temporal knowledge graph | **Threats:** Graphiti requires Neo4j/FalkorDB + OpenAI API (heavy infra for M1); gws is pre-v1 (no stability guarantees); Bright Data adds external dependency for core functionality; Markowitz/rebalancing add complexity without clear payoff at current scale |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **Google Workspace CLI** (unlocks entire Google ecosystem, built-in MCP, ~2hr setup), **Bright Data MCP** (supercharges investigate module, free tier, ~1hr setup) | **Code Executor MCP** (sandboxed Python execution exists via subprocess, marginal gain) |
| **Low Priority** | **Graphiti MCP** (transformative for memory but requires Neo4j + OpenAI + Docker, wait for M5 Ultra), **Dynamic Rebalancing** (APScheduler already handles scheduling, premature optimization) | **Markowitz Optimization** (no meaningful resource allocation problem at current scale), **Gitingest MCP** (Claude Code already has full repo context, CLI Sprint 4 solved this) |

---

## Candidate-by-Candidate Analysis

### 1. Markowitz Optimization for Resource/Model Allocation

**What it is:** Modern Portfolio Theory (mean-variance optimization) applied to allocating inference requests across model tiers (Primary/Coding/Complex/Cloud) based on "return" (quality) vs "risk" (latency/cost).

**Argue (Best Case):**
- Elegant mathematical framework for multi-objective optimization
- Could balance quality, latency, and cost across 4 model tiers
- Libraries exist (PyPortfolioOpt, scipy.optimize) -- pure Python, no infra
- Could optimize the cloud spillover threshold dynamically based on observed performance

**Refute (Devil's Advocate):**
- Hestia has 2 active local models and 1 cloud tier. This is a 3-asset portfolio. Markowitz is designed for 30+ asset portfolios where covariance matters.
- The current keyword-based routing (`complex_patterns` in inference.yaml) is deterministic, interpretable, and fast. It routes in microseconds.
- "Return" and "risk" for model routing are not well-defined continuous variables -- quality is subjective, latency is bimodal (local vs cloud), cost is binary (free vs paid).
- The covariance matrix (central to Markowitz) requires historical performance data across model pairs. Hestia doesn't collect this telemetry.
- Over-engineering: the entire routing decision happens in `_matches_routing_patterns()` in ~20 lines. Replacing this with an optimization solver adds complexity for zero user-visible improvement.
- M1 constraint means only one model fits in GPU at a time anyway -- there's no parallel allocation to optimize.

**Verdict: SKIP.** The problem Markowitz solves (optimal allocation across many correlated assets) does not exist in Hestia's 2-3 model routing. Revisit only if hardware upgrade enables simultaneous model loading (M5 Ultra with 192GB).

---

### 2. Dynamic Rebalancing for Scheduled Task Reallocation

**What it is:** Automatically reallocating scheduled tasks (Orders) based on system load, time-of-day patterns, and resource availability.

**Argue (Best Case):**
- Could prevent inference pile-ups (e.g., daily briefing + memory ingestion + principle distillation all hitting at 3 AM)
- Research shows multi-agent reinforcement learning achieves strong results for dynamic job scheduling (Nature, 2025)
- APScheduler supports dynamic job modification -- the hooks exist
- Could improve responsiveness by deferring background tasks when user is actively chatting

**Refute (Devil's Advocate):**
- Hestia currently has ~3-5 scheduled tasks (daily briefing, memory ingestion, principle distillation, session cleanup). This is not a scheduling problem that needs dynamic rebalancing.
- APScheduler already handles cron-style scheduling with `max_instances=1` to prevent overlap.
- The M1 has one GPU. Tasks are sequential by nature. There's nothing to "rebalance" -- tasks queue naturally.
- Adding RL-based scheduling for 5 tasks is like deploying Kubernetes for 2 containers.
- The real bottleneck is inference latency, not scheduling. A task waiting 30s for the model is normal.
- Complexity cost: monitoring, telemetry collection, policy training, edge cases when the rebalancer makes wrong decisions.

**Verdict: SKIP.** Premature optimization. The current cron-based APScheduler with fixed schedules is appropriate for the task volume. Revisit when task count exceeds ~20 or when multi-model parallel inference becomes possible.

---

### 3. Code Executor MCP

**What it is:** An MCP server that lets LLMs execute Python code in a sandboxed Conda environment.

**Argue (Best Case):**
- Enables Hestia to run arbitrary Python for data analysis, calculations, file transformations
- Anthropic research shows 98.7% reduction in context overhead when tools are expressed as executable code vs JSON schemas
- Could replace multiple single-purpose tools with one general-purpose executor
- Sandboxed via Conda environment -- safer than raw subprocess

**Refute (Devil's Advocate):**
- Hestia already has `run_command` tool with subprocess sandboxing (`execution.yaml` config: blocked commands, allowed directories, timeout limits)
- The existing sandbox is more restrictive (allowlist-based) which is actually better for a personal assistant than a Conda environment
- Code execution is a significant security surface. Hestia's security posture (double encryption, biometric auth, communication gate) would need careful integration.
- The "98.7% context reduction" applies to agents managing 100+ MCP tools. Hestia has 20 Apple tools + ~10 system tools. The problem doesn't exist at this scale.
- Qwen 3.5 9B's code generation quality is decent but not reliable enough for unsupervised execution. Bad code + auto-execution = data loss risk.
- Would require: MCP client integration, Conda environment management, output capture/sanitization, security review.

**Verdict: LOW PRIORITY.** The existing `run_command` tool with path sandboxing covers the primary use case. The Anthropic context-reduction research is compelling but targets agents with 100+ tools, not Hestia's 30. Consider when tool count grows significantly or when upgrading to a more capable local model.

---

### 4. Gitingest MCP

**What it is:** An MCP server that ingests Git repositories into LLM-friendly text digests (summary, file tree, content).

**Argue (Best Case):**
- Could let Hestia analyze external repositories on demand ("what does this GitHub project do?")
- Supports filtering by patterns, file size limits, branch selection
- Simple single-tool interface, low integration complexity
- Could complement the investigate module for GitHub URL analysis

**Refute (Devil's Advocate):**
- CLI Sprint 4 already built repo context injection with `MAX_CHARS_PER_FILE=4000`, `MAX_TOTAL_CHARS=16000`, priority-based file selection. This solves the local repo case.
- For external repos, the investigate module already handles URL content extraction (WebArticleExtractor, YouTubeExtractor). Adding a GitExtractor to the existing pipeline would be more architecturally consistent than bolting on another MCP server.
- Gitingest runs locally -- on M1 16GB, ingesting a large repo (e.g., linux kernel) would consume significant memory and time.
- The primary user (Andrew) uses Claude Code for development work. Claude Code already has full repo context built in. Hestia doesn't need to duplicate this capability.
- Private repo support requires GitHub token management -- another credential to secure.

**Verdict: LOW PRIORITY.** The use case (external repo analysis) is real but niche. If needed, building a `GitHubExtractor` for the investigate module is cleaner than adding an MCP dependency. The local repo case is already solved by CLI Sprint 4.

---

### 5. Graphiti MCP (Knowledge Graph with Temporal Memory)

**What it is:** A framework for building temporally-aware knowledge graphs where facts have validity windows, entities evolve over time, and queries can be scoped to "what was true at time T."

**Argue (Best Case):**
- Directly addresses the weakness in Hestia's current `graph_builder.py` -- which builds a static graph from memory chunks with simple topic/entity co-occurrence, no temporal awareness, no LLM-powered entity extraction.
- Temporal fact management is exactly what Hestia needs: user preferences change, projects evolve, health metrics shift. The current `TemporalDecay` applies a decay curve but doesn't model fact validity windows.
- Would dramatically improve the Research module -- currently `graph_builder.py` is limited to 200 nodes with basic co-occurrence edges. Graphiti builds semantically rich entity-relationship graphs.
- MCP server interface means it can be adopted incrementally alongside existing ChromaDB memory.
- FalkorDB claims 496x faster P99 latency vs Neo4j -- relevant for real-time agent queries.
- Could power the deferred MetaMonitor (Sprint 11B) with much richer behavioral pattern detection.

**Refute (Devil's Advocate):**
- **Infrastructure burden is heavy:** Requires Neo4j or FalkorDB (Docker container, 1-2GB RAM), plus OpenAI API key for entity extraction and embeddings. On M1 16GB with Ollama already consuming 8-10GB, adding a graph database is a tight fit.
- Graphiti "works best with LLM services that support Structured Output (such as OpenAI and Gemini)" -- meaning it needs cloud LLM calls for ingestion. This conflicts with Hestia's default local-only privacy posture.
- Migration complexity: Hestia has ~1600+ memory chunks in ChromaDB. Migrating to or syncing with Graphiti is non-trivial.
- The current graph_builder.py, while simple, serves the visualization use case (Neural Net view) adequately. Graphiti solves a different, deeper problem.
- FalkorDB is a startup -- long-term viability uncertain vs Neo4j Community Edition.

**Verdict: DEFER TO HARDWARE UPGRADE.** This is the highest-impact candidate but requires infrastructure that doesn't fit on M1 16GB comfortably. When the M5 Ultra Mac Studio arrives (192GB unified memory per the upgrade playbook in `docs/plans/`), Graphiti + FalkorDB becomes the obvious memory upgrade path. Worth prototyping in a Docker environment on the dev Mac to validate integration patterns before the hardware arrives.

---

### 6. Bright Data Web MCP

**What it is:** An MCP server that provides web scraping, search engine access, and structured data extraction through a single interface. Free tier: 5,000 requests/month.

**Argue (Best Case):**
- **Direct upgrade to the investigate module.** Currently, `WebArticleExtractor` and `YouTubeExtractor` do basic content extraction. Bright Data adds: bot-detection bypass, CAPTCHA solving, JavaScript rendering, structured data extraction from Amazon/LinkedIn/etc.
- Free tier (5K requests/month, no credit card) is generous for personal use. Andrew likely runs <100 investigations/month.
- Already has an MCP server -- integration is configuration, not code.
- Enables new capabilities: search engine scraping (Google/Bing results as structured data), batch scraping, browser automation for dynamic content.
- 76.8% success rate (highest in MCP benchmarks) vs likely lower rate for raw HTTP extraction.
- Pairs naturally with the existing investigate pipeline: Bright Data extracts content, LLM analyzes it.

**Refute (Devil's Advocate):**
- Adds external service dependency. If Bright Data goes down or changes pricing, investigate module degrades.
- Privacy: all URLs being investigated are sent to Bright Data's infrastructure. For personal research this is likely fine, but it's a data flow to be aware of.
- The existing extractors work for most cases (articles, YouTube). The upgrade matters mainly for JS-heavy sites and sites with bot protection.
- 5K free requests seems generous but batch operations (`scrape_batch`, `search_engine_batch`) consume multiple requests per call.
- Pro mode features (structured extraction from specific sites) are paid.

**Verdict: ADOPT.** High value, near-zero effort. Configure as an MCP server, wire into the investigate module as a premium extraction backend (try Bright Data first, fall back to existing extractors). The free tier more than covers personal use. Setup time: ~1 hour.

---

### 7. Google Workspace CLI (gws)

**What it is:** Google's official CLI for all Workspace APIs (Gmail, Calendar, Drive, Docs, Sheets, Chat, Admin). Written in Rust, distributed via npm, with built-in MCP server (`gws mcp`). Released March 2026.

**Argue (Best Case):**
- **Unlocks the entire Google ecosystem** that Hestia currently cannot touch. Hestia has 20 Apple tools (Calendar, Reminders, Notes, Mail) but zero Google integration. If Andrew uses Gmail, Google Calendar, or Google Drive at all, this is a massive capability gap.
- Built-in MCP server (`gws mcp -s gmail,calendar,drive`) -- zero custom code needed.
- 100+ agent skills and 50+ curated recipes built in.
- OAuth credentials stored in macOS Keychain with AES-256-GCM -- aligns with Hestia's security posture.
- Dynamic API surface: reads Google Discovery Service at runtime, so new Google APIs are automatically available.
- JSON output on every command -- trivially parseable by Hestia's tool executor.
- Could be wired as tools in the existing ToolRegistry, or used directly via MCP.
- Enables cross-ecosystem workflows: "Move my Google Calendar events to Apple Calendar," "Draft a Gmail reply based on this Apple Note."

**Refute (Devil's Advocate):**
- **Pre-v1 software**: Google explicitly says "no SLA guarantees, no formal support, no backward compatibility promises." Command syntax may change between releases.
- Requires a Google Cloud project with OAuth consent screen configured. For personal use this is straightforward but not zero-effort.
- Scope creep risk: 100+ skills across all Workspace APIs. Need to carefully limit which services are exposed to Hestia to avoid tool explosion (currently 30 tools -- adding 100 would overwhelm the local model).
- If Andrew is fully in the Apple ecosystem (iCloud, Apple Mail, Apple Calendar), the Google integration adds no value.
- npm dependency for a Rust binary is an unusual distribution choice. Updates may lag or break.

**Verdict: ADOPT (if Google ecosystem is used).** If Andrew uses any Google services, this is the single highest-value addition. The built-in MCP server makes integration near-trivial. Start with `gws mcp -s gmail,calendar,drive` (3 services) and expand as needed. Setup time: ~2 hours (Google Cloud project + OAuth + MCP config). Skip entirely if Apple-only.

---

## Third-Party Evidence

- **MCP ecosystem maturity:** 200+ MCP servers as of February 2026. The protocol is now under the Linux Foundation (donated December 2025). This is no longer experimental -- it's industry standard.
- **Anthropic's code execution research** validates the MCP-as-code-execution pattern but at a scale (100+ tools) that Hestia doesn't operate at.
- **Gartner predicts** 40% of enterprise apps will have task-specific AI agents by end of 2026, up from 5% in 2025. Hestia is ahead of the curve here.
- **Graphiti adoption:** Used by multiple production AI assistants. FalkorDB partnership adds a lightweight alternative to Neo4j. The project has 14K+ GitHub stars.
- **Google Workspace CLI** received significant coverage (VentureBeat, Medium, Technology.org) within days of release. Early adoption is high.

---

## Recommendation

**Immediate (Sprint 12 or next session):**
1. **Bright Data MCP** -- Configure as extraction backend for investigate module. Free tier, ~1hr.
2. **Google Workspace CLI** -- Install, OAuth setup, wire `gws mcp` for Gmail/Calendar/Drive. ~2hrs. (Only if Andrew uses Google services.)

**Deferred (M5 Ultra hardware upgrade):**
3. **Graphiti MCP** -- Prototype on dev Mac in Docker, plan migration path from ChromaDB. Full adoption when 192GB RAM available.

**Skip:**
4. **Markowitz Optimization** -- No meaningful problem to solve at current scale.
5. **Dynamic Rebalancing** -- APScheduler is sufficient for 5 scheduled tasks.
6. **Code Executor MCP** -- Existing `run_command` sandbox covers the use case.
7. **Gitingest MCP** -- Claude Code and CLI Sprint 4 already solve repo context.

**Confidence: High.** The two adopt recommendations have clear value propositions, low integration effort, and minimal risk. The skip recommendations are grounded in the specific constraints of Hestia's architecture (M1 16GB, 30 tools, 5 scheduled tasks, Apple-primary ecosystem).

---

## Final Critiques

- **Skeptic ("Why won't this work?"):** "Bright Data's free tier will get rate-limited or deprecated. Google Workspace CLI is pre-v1 and will break." **Response:** Both are additive -- Hestia's existing investigate and Apple tools continue to work. These are enhancement layers, not replacements. If Bright Data deprecates the free tier, fall back to existing extractors. If gws breaks, the Apple ecosystem tools are unaffected.

- **Pragmatist ("Is the effort worth it?"):** "You're adding two external dependencies for a personal assistant that already works." **Response:** Bright Data is 1 hour of config for dramatically better web extraction. Google Workspace CLI is 2 hours for an entirely new ecosystem. The effort-to-capability ratio is exceptional. Compare to Sprint 11.5 which was ~15 hours for memory pipeline improvements.

- **Long-Term Thinker ("What happens in 6 months?"):** "With the M5 Ultra, all of these become feasible. Should you just wait?" **Response:** Bright Data and gws should be adopted now -- they're orthogonal to hardware. Graphiti is correctly deferred. The skip items remain skippable regardless of hardware. The risk of waiting on Bright Data/gws is missing 6 months of improved web extraction and Google integration for zero cost.

---

## Open Questions

1. **Does Andrew use Google services?** If Apple-only, skip gws entirely and reallocate that assessment to other candidates.
2. **Bright Data privacy review:** Should URLs sent to Bright Data be filtered through the existing communication gate? Or is the investigate module already an explicit user-initiated action that implies consent?
3. **Graphiti prototype timeline:** When is the M5 Ultra expected? Should a Docker-based prototype be built on the dev Mac in advance?
4. **MCP client integration:** Hestia's tool registry currently uses a custom format. What's the cleanest path to consuming MCP servers -- build a generic MCP client adapter, or wrap each MCP server's tools individually?

---

Sources:
- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [Graphiti MCP Server (FalkorDB)](https://docs.falkordb.com/agentic-memory/graphiti-mcp-server.html)
- [Google Workspace CLI (GitHub)](https://github.com/googleworkspace/cli)
- [Google Workspace CLI (VentureBeat)](https://venturebeat.com/orchestration/google-workspace-cli-brings-gmail-docs-sheets-and-more-into-a-common)
- [gws npm package](https://www.npmjs.com/package/@googleworkspace/cli)
- [Bright Data MCP (GitHub)](https://github.com/brightdata/brightdata-mcp)
- [Bright Data MCP Free Tier](https://brightdata.com/blog/ai/web-mcp-free-tier)
- [Bright Data MCP Pricing](https://brightdata.com/pricing/mcp-server)
- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [MCP 2026 Roadmap](http://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/)
- [Gitingest MCP (LobeHub)](https://lobehub.com/mcp/narumiruna-gitingest-mcp)
- [MCP Specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25)
- [Decentralized Task Allocation (Nature 2025)](https://www.nature.com/articles/s41598-025-21709-9)
- [Gartner AI Agent Predictions](https://www.gartner.com/en/newsroom/press-releases/2025-08-26-gartner-predicts-40-percent-of-enterprise-apps-will-feature-task-specific-ai-agents-by-2026-up-from-less-than-5-percent-in-2025)
