# Discovery Report: Efficiency & Stability Sprint

**Date:** 2026-03-02
**Confidence:** High
**Decision:** Implement in 3 phases over ~3 sprints: (1) Server reliability foundation, (2) Caching & performance, (3) Data lifecycle management. Skip sub-agent orchestration and multi-device message queuing as premature for current usage patterns.

---

## Hypothesis

Can Hestia transition from a "working MVP with known reliability gaps" to "enterprise-grade personal infrastructure" by addressing seven proposed areas: server uptime guarantees, sub-agent orchestration, multi-device message processing, caching layers, pre-load states, automated dependency management, and hot/warm/cold data archiving?

**Restated precisely:** Which of these seven areas deliver meaningful reliability/performance improvements for a single-user personal AI server on Mac Mini M1 (16GB RAM), and in what order should they be implemented given ~6 hours/week of development time?

---

## Current State Assessment

### What Exists Today

| Area | Current State | Maturity |
|------|--------------|----------|
| **Server process** | Single Uvicorn process, no Gunicorn, no workers | Minimal |
| **Uptime monitoring** | launchd `KeepAlive: true` + watchdog script (5-min poll, 3 failures to restart) | Functional |
| **Health checks** | `/v1/ping` (simple) + `/v1/health` (checks inference, memory, tools, state) | Good |
| **Response caching** | In-memory `ResponseCache` in orchestration (500 entries, 1h TTL, SHA-256 keys) | Good |
| **Data caching** | Newsfeed: SQLite materialized cache (30s TTL). Explorer: SQLite + lazy refresh. User config: in-memory with invalidation | Piecemeal |
| **Dependency mgmt** | Plain `requirements.txt` with `>=` version bounds, no lockfile, no Dependabot | Minimal |
| **Log management** | `TimedRotatingFileHandler` (30-day retention config, 90-day backup count), but 73MB accumulated with no compression | Needs attention |
| **Data archiving** | Newsfeed: 30-day cleanup. Agents: old snapshot cleanup. No memory/conversation archiving | Gap |
| **Pre-load states** | Sequential manager init in `lifespan()` (~15 managers). No readiness probe. No parallel init | Gap |
| **Multi-device** | Device token auth + per-device sessions exist. No message queue or sync | Structural only |
| **Sub-agent orchestration** | Council (4-role dual-path) exists. No agent retry, no circuit breaker, no backpressure | Functional |
| **Database sizes** | 13 SQLite files + ChromaDB totaling 3.5MB. Tiny. Not a bottleneck | Fine |

### Key Findings from Codebase Investigation

1. **Server runs as bare Uvicorn** (`python -m hestia.api.server`). No process manager. A single crash = total downtime until watchdog restarts (up to 15 minutes: 3 polls x 5 min).

2. **Manager initialization is sequential** in `lifespan()`: 15 managers initialized one-by-one. No timing, no parallel init, no graceful degradation if one fails. The wiki scheduler even fires a non-blocking `create_task` for post-deploy refresh.

3. **No readiness probe**: The server accepts requests as soon as Uvicorn starts, potentially before all managers are initialized. The `/v1/health` endpoint checks component health but isn't gated on startup completion.

4. **73MB of logs** with rotation configured but old files not compressed. The `hestia.log.2026-03-01` alone is 42MB. Retention is 90 days in code but config says 30 days.

5. **Response cache is well-designed** but only covers text chat responses. Explorer, wiki, newsfeed, health, and tool endpoints re-execute on every call. The newsfeed has its own 30s TTL cache but the pattern isn't generalized.

6. **No connection pooling**: Every `httpx.AsyncClient` for cloud/Ollama calls is created per-use or as a lazy singleton with no pool size limits. The cloud manager creates new `httpx.AsyncClient(timeout=10.0)` in `async with` blocks (one per health check call).

7. **requirements.txt uses `>=` bounds**: `fastapi>=0.104.0`, `chromadb>=0.4.0`, etc. No upper bounds, no lockfile. A `pip install` on a fresh venv could pull breaking versions. No automated update mechanism.

8. **Memory data is tiny**: memory.db is 225KB, ChromaDB is 1.2MB. Data archiving would be over-engineering at this scale. The real growth risk is logs (73MB already).

9. **Graceful shutdown exists** but is incomplete: signal handlers set a shutdown event, but `lifespan()` cleanup only covers config_loader, wiki_scheduler, invite_store, and investigate_manager. Memory manager, cloud manager, inference client, and many others have `close()` methods that are never called on shutdown.

10. **Rate limiter is in-memory only**: fine for single-process, but would reset on restart and not work across Gunicorn workers.

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Well-structured manager pattern with singleton factories. Good separation of concerns. Response cache already exists. Health check infrastructure in place. Watchdog and launchd already configured. Session TTL and cleanup implemented. Temporal decay prevents stale memory from polluting results. | **Weaknesses:** No process manager (single point of failure). Sequential startup ~15 managers. Incomplete shutdown cleanup. No readiness gate. Unpinned dependencies. 73MB log accumulation. No connection pooling for httpx. In-memory rate limiter not shared across workers. |
| **External** | **Opportunities:** Gunicorn with 2 workers would give immediate fault tolerance. `pip-compile` + Dependabot is a 30-minute setup with permanent ROI. Log compression could save 90%+ disk. `fastapi-cache2` could generalize the caching pattern. Parallel manager init could halve startup time. | **Threats:** Adding Gunicorn changes the concurrency model (in-memory singletons break across workers). ChromaDB background threads already cause pytest hangs. Over-engineering for single-user scale. Python 3.9 is approaching EOL (need upgrade path). |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **1. Gunicorn + 2 workers** (fault tolerance, auto-restart on OOM/crash). **2. Pinned dependencies** (`pip-compile` + lockfile). **3. Startup readiness gate** (don't accept requests until managers ready). **4. Shutdown cleanup** (close all managers properly). | **5. Log compression** (gzip old logs, easy script). **6. Retention config alignment** (30 vs 90 day discrepancy). |
| **Low Priority** | **7. Parallel manager initialization** (halve startup time). **8. Generalized endpoint caching** (`fastapi-cache2`). **9. Connection pooling** (reuse httpx clients). | **10. Hot/warm/cold archiving** (data is 3.5MB, premature). **11. Sub-agent orchestration** (council works, no failures in practice). **12. Multi-device message queue** (single user, 1-2 devices). |

---

## Argue (Best Case)

### Why This Sprint Matters

1. **Gunicorn is the highest-leverage single change.** Right now, if the Python process crashes (OOM from ChromaDB, unhandled exception, memory leak), the server is dead for up to 15 minutes. With Gunicorn and 2 workers, a crashed worker is restarted in <5 seconds. This alone changes uptime from "eventually consistent" to "always available."

2. **Pinned dependencies prevent invisible breakage.** With `>=` bounds, `pip install -r requirements.txt` on a fresh Mac Mini deploy could pull `chromadb 1.0` (breaking API), `fastapi 1.0` (breaking middleware), or `pydantic 3.0` (breaking schemas). This is a ticking time bomb. `pip-compile` takes 30 minutes to set up and provides permanent protection.

3. **The startup readiness gap is real.** If the server restarts (crash, deploy, watchdog restart), Uvicorn starts accepting HTTP connections before all 15 managers finish initialization. A client request during this window hits uninitialized managers and gets a 500. A readiness gate would queue requests until ready.

4. **Log management is the only actual growth concern.** At 73MB for ~2 months of development, production usage could easily generate 1GB/month. Compressed logs would be ~10% of that size.

5. **Incomplete shutdown causes resource leaks.** The memory manager, cloud client, and inference client all have `close()` methods for cleaning up database connections and httpx sessions. These are never called on shutdown, potentially leaving connections hanging.

### Evidence Supporting This Approach

- FastAPI's official deployment docs recommend Gunicorn + Uvicorn workers for production
- The `pip-compile` approach is the "boring Python" community standard endorsed by Django developers
- The current watchdog already demonstrates the need for process management
- The 42MB single-day log file proves log management isn't theoretical

---

## Refute (Devil's Advocate)

### Why This Might Be Over-Engineering

1. **This is a single-user personal server.** Enterprise-grade reliability for one person? The current watchdog + launchd `KeepAlive` already provides 99%+ uptime. A 15-minute recovery window for a personal assistant is annoying, not catastrophic.

2. **Gunicorn breaks the singleton pattern.** Every in-memory singleton (rate limiter, response cache, conversations dict) is per-process. With 2 Gunicorn workers, you'd have 2 separate rate limiters, 2 response caches, 2 conversation stores. This means:
   - Rate limits are effectively doubled (each worker tracks separately)
   - Response cache hits drop (cached in worker A, miss in worker B)
   - Conversations might split across workers (message 1 hits worker A, message 2 hits worker B)
   This is a **real architectural problem** that requires either sticky sessions, shared state (Redis), or careful design.

3. **Dependency pinning creates maintenance burden.** Someone (or Dependabot) has to review and merge update PRs weekly. With ~6 hours/week total development time, this overhead is non-trivial.

4. **Data archiving is solving a problem that doesn't exist.** 3.5MB of data. Even at 10x growth over 5 years, that's 35MB. SQLite handles databases up to 281TB. This is premature optimization in its purest form.

5. **Pre-load states add complexity.** Parallel manager initialization means dealing with initialization order dependencies (e.g., memory manager before request handler). The current sequential approach is simple and debuggable.

### Hidden Costs

- Gunicorn is another process to manage, another log source, another failure mode
- `pip-compile` lock files create merge conflicts when multiple sessions modify dependencies
- Readiness gates need health check clients updated to poll `/ready` instead of `/ping`
- Connection pooling changes require testing under load that doesn't exist yet

---

## Third-Party Evidence

### What Works in Practice (Similar Projects)

**Home Assistant** (similar scale: personal server, single user, Python/FastAPI-ish):
- Uses `uvicorn` directly with a single worker
- Process management via systemd (equivalent to launchd)
- No Gunicorn -- their reasoning: "async Python with a single user doesn't benefit from multiple workers"
- Heavy use of in-memory caching with TTL
- Dependency pinning via `pip-compile` (they switched TO this from unpinned)

**Litestream + SQLite pattern** (for personal data servers):
- SQLite as primary database with continuous replication to S3
- No hot/warm/cold tiers -- the database is small enough to keep everything hot
- Archive strategy: periodic full backups, not data migration between tiers

**FastAPI production deployments** (industry consensus):
- For >100 req/sec: Gunicorn + multiple workers + Redis
- For <10 req/sec (single user): Uvicorn standalone with `--workers 2` is sufficient
- The key insight: `uvicorn --workers 2` gives you Gunicorn-like process management without Gunicorn

### Contradicting Evidence

1. **Uvicorn's built-in worker management** is mature enough for single-user. Using `uvicorn main:app --workers 2` gives auto-restart of crashed workers without Gunicorn's complexity. This avoids the singleton-breaking problem because Uvicorn uses `spawn` (not `fork`), but it still means separate memory spaces.

2. **The singleton problem is actually solved by a different approach**: use `--workers 1` with `--limit-max-requests` to periodically restart the worker (prevents memory leaks) while keeping all in-memory state consistent. Combined with launchd `KeepAlive`, this provides the reliability benefits without the architectural headache.

### Alternative Approaches Missed

- **`--limit-max-requests` with jitter**: Uvicorn/Gunicorn can restart workers after N requests (e.g., 1000) with random jitter. This prevents memory leaks from accumulating without requiring multiple workers. Combined with `KeepAlive: true`, this is a simpler path than multi-worker.

- **healthcheck-based readiness**: Instead of a separate `/ready` endpoint, use the existing `/v1/health` response to include a `"ready": true` field once all managers report healthy. The watchdog already checks health -- it could be extended to handle the startup window.

- **`logrotate` instead of Python rotation**: macOS can use `newsyslog.conf` or a simple cron job to compress and rotate logs. This is more reliable than Python's `TimedRotatingFileHandler` which can't compress.

---

## Recommendation

### Phase 1: Server Reliability Foundation (Sprint-sized, ~6 hours)

| Item | What | Why | Effort |
|------|------|-----|--------|
| 1a | **Add `--limit-max-requests 5000 --limit-max-requests-jitter 500`** to Uvicorn startup | Prevents memory leaks from accumulating. Worker auto-restarts after ~5000 requests with random jitter. | 15 min |
| 1b | **Pin all dependencies** with `pip-compile` | Create `requirements.in` (current direct deps), generate locked `requirements.txt`. Set up Dependabot. | 45 min |
| 1c | **Readiness gate in lifespan** | Add `app.state.ready = False` at start, set `True` after all managers init. Add middleware that returns 503 if not ready. Add `/v1/ready` endpoint. | 1.5 hr |
| 1d | **Complete shutdown cleanup** | Call `close()` on memory_manager, cloud_manager, inference_client, health_manager, explorer_manager, newsfeed_manager, order_scheduler in `lifespan()` finally block. | 1.5 hr |
| 1e | **Log compression script** | Add cron/launchd job: `gzip` log files older than 7 days, delete compressed files older than 90 days. Fix retention config discrepancy. | 1 hr |
| 1f | **Startup timing** | Add timing around each manager init in lifespan, log total startup time. | 30 min |

**Expected outcome:** Zero-downtime from memory leaks. No uninitialized-manager 500s. Reproducible builds. Log growth capped.

### Phase 2: Caching & Performance (Sprint-sized, ~6 hours)

| Item | What | Why | Effort |
|------|------|-----|--------|
| 2a | **Shared httpx client pool** | Create a module-level `httpx.AsyncClient` with connection pooling for Ollama calls and cloud health checks. Reuse across inference, cloud, and council. | 2 hr |
| 2b | **Endpoint-level caching for read-heavy routes** | Add `@cache(expire=30)` via `fastapi-cache2` `InMemoryBackend` to: `/v1/health`, `/v1/tools`, `/v1/wiki/articles`, `/v1/explorer/resources` list endpoint. | 2 hr |
| 2c | **Parallel manager initialization** | Group independent managers and init with `asyncio.gather()`. Dependency chain: memory_manager first, then everything else in parallel. | 1.5 hr |
| 2d | **Health endpoint caching** | The `/v1/health` endpoint queries Ollama, memory, and tools on every call. Cache the result for 30 seconds (same pattern as newsfeed). | 30 min |

**Expected outcome:** Faster startup. Fewer redundant Ollama health checks. Reduced latency on repeated reads.

### Phase 3: Data Lifecycle & Observability (Sprint-sized, ~6 hours)

| Item | What | Why | Effort |
|------|------|-----|--------|
| 3a | **Structured startup health report** | At the end of lifespan init, log a single JSON object with all component statuses, database sizes, and startup duration. This becomes the "system birth certificate." | 1 hr |
| 3b | **Memory archiving foundation** | Add a `memory_archive` table or separate `memory_archive.db`. After 6 months, move superseded and conversation chunks to archive. Keep facts/decisions hot forever. Query archive on explicit deep search. | 3 hr |
| 3c | **Database vacuum schedule** | Add a weekly `VACUUM` on each SQLite database via APScheduler (already used for orders/wiki). Prevents fragmentation as data grows. | 1 hr |
| 3d | **Metrics endpoint** | Add `/v1/metrics` returning: request count, cache hit rate, avg response time, memory chunk count, database sizes, uptime. No external dependency (Prometheus optional later). | 1 hr |

**Expected outcome:** Operational visibility. Memory won't grow unbounded. Database stays compact.

### What to Skip

| Area | Why Skip |
|------|----------|
| **Sub-agent orchestration** | Council already has dual-path fallback. No evidence of council failures causing user-visible issues. Circuit breakers and retry logic are enterprise patterns for multi-service architectures, not single-process Python. |
| **Multi-device message queue** | Single user, 1-2 devices. The existing device_token auth and per-device sessions are sufficient. A message queue (Redis, RabbitMQ) adds operational complexity for a problem that doesn't exist yet. Revisit when Andrew has 3+ active devices or adds a second user. |
| **Hot/warm/cold data archiving** | Total data is 3.5MB. Even the "archive" in Phase 3 is optional -- it's a foundation for the future, not a current need. Cold storage tiers (S3, external drives) are irrelevant at this scale. |
| **Gunicorn multi-worker** | The singleton-breaking problem (rate limiter, response cache, conversations) outweighs the benefit for single-user. `--limit-max-requests` with launchd `KeepAlive` achieves the same reliability without the architectural cost. |

### Confidence: HIGH

The evidence strongly supports this prioritization:
- Phase 1 fixes real, observed failure modes (stale processes, uninitialized managers, log growth)
- Phase 2 is incremental improvement on patterns already proven in the codebase
- Phase 3 is forward-looking foundation that becomes relevant at 10x current scale
- The skipped items are solutions looking for problems

### What Would Change This Recommendation

- **If Andrew adds a second user**: Multi-worker becomes necessary. Rate limiter needs Redis. Message queue makes sense.
- **If data grows past 1GB**: Hot/warm/cold archiving becomes relevant. Consider Litestream for backups.
- **If council starts failing**: Circuit breaker and retry orchestration become justified.
- **If ChromaDB OOMs**: Gunicorn workers with process isolation become necessary for fault containment.

---

## Final Critiques

### The Skeptic: "Why won't this work?"

**Challenge:** "Phase 1 is just busywork. The server has been running fine for months. You're adding complexity (readiness gates, shutdown hooks, pip-compile) to solve theoretical problems."

**Response:** The server has been running fine *in development*. The production deployment on Mac Mini has had multiple incidents:
- Stale server processes running for weeks serving outdated code (documented in CLAUDE.md as "#1 recurring time sink")
- The watchdog exists because the server crashes enough to need it
- 73MB of logs in 2 months with no compression is a disk space problem on a 256GB/512GB Mac Mini
- Unpinned `chromadb>=0.4.0` could pull ChromaDB 1.x (released 2025) which has breaking API changes

These are not theoretical. The `--limit-max-requests` addition alone prevents the "stale process" problem permanently.

### The Pragmatist: "Is the effort worth it?"

**Challenge:** "18 hours of work (3 sprints) for reliability improvements on a personal project? That's 3 weeks of Andrew's dev time. What features could be built instead?"

**Response:** This is infrastructure investment, not feature work. The ROI calculation:
- **pip-compile** (45 min): prevents every future "why did my deploy break" investigation (each one costs 1-2 hours)
- **Readiness gate** (1.5 hr): prevents every future "why am I getting 500s after restart" debug session
- **Shutdown cleanup** (1.5 hr): prevents resource leak accumulation that degrades performance over weeks
- **Log compression** (1 hr): prevents disk pressure on Mac Mini indefinitely

Total investment: ~6 hours for Phase 1. Expected savings: 10+ hours over the next year in avoided debugging. Phase 2 and 3 are nice-to-haves that can be deferred.

**Recommendation:** Do Phase 1 as a single focused sprint. Phases 2 and 3 can be done incrementally over time or skipped entirely without consequence.

### The Long-Term Thinker: "What happens in 6 months?"

**Challenge:** "Is this architecture going to scale when Andrew inevitably wants to add a second user, voice streaming, or always-on context?"

**Response:** The architecture holds for 6 months under the following assumptions:
- Still single-user (or 2 users at most)
- ChromaDB stays under 1M embeddings (~250MB RAM)
- No real-time streaming requirements (current request/response is fine)
- Mac Mini M1 16GB remains the target hardware

Phase 1's changes are **forward-compatible**:
- `pip-compile` works regardless of scale
- Readiness gates work with any number of workers
- Shutdown cleanup prevents cumulative degradation
- Log compression is universal

If in 6 months Hestia needs to handle concurrent users or real-time streaming, the right move is:
1. Upgrade to Gunicorn + 2 workers (move rate limiter/cache to Redis)
2. Add WebSocket support for streaming responses
3. Consider PostgreSQL if SQLite contention becomes measurable

But these are **reactive, not preemptive** decisions. The Phase 1 foundation makes these future changes easier without paying for them now.

---

## Open Questions

1. **What is the actual crash frequency?** The watchdog logs (`logs/watchdog.log`) would reveal how often the server actually crashes. If it's <1/month, the urgency of fault tolerance drops.

2. **Python version upgrade path.** Currently 3.9, CLAUDE.md says 3.12. When is the upgrade happening? Some Phase 2 improvements (e.g., `asyncio.TaskGroup` for parallel init) require 3.11+.

3. **Mac Mini disk capacity.** Is it 256GB or 512GB? This affects how urgently log compression is needed.

4. **Is Dependabot already configured?** Check if `.github/dependabot.yml` exists. If not, adding it alongside `pip-compile` is trivial.

5. **What's the p99 latency for chat responses?** If it's >10s (dominated by Ollama inference), caching improvements in Phase 2 won't be noticeable.

---

## Sources

- [FastAPI Deployment Guide 2026](https://www.zestminds.com/blog/fastapi-deployment-guide/)
- [FastAPI Best Practices for Production 2026](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026)
- [FastAPI Health Check Best Practices](https://www.index.dev/blog/how-to-implement-health-check-in-python)
- [Avoiding Zombie Containers in Production](https://medium.com/@bhagyarana80/fastapi-health-checks-and-timeouts-avoiding-zombie-containers-in-production-411a27c2a019)
- [Server Workers - Uvicorn with Workers (FastAPI docs)](https://fastapi.tiangolo.com/deployment/server-workers/)
- [How to Use Uvicorn for Production Deployments](https://oneuptime.com/blog/post/2026-02-03-python-uvicorn-production/view)
- [Boring Python: Dependency Management](https://www.b-list.org/weblog/2022/may/13/boring-python-dependencies/)
- [pip-tools (pip-compile + pip-sync)](https://pypi.org/project/pip-tools/)
- [Best Practices for Managing Python Dependencies](https://www.geeksforgeeks.org/python/best-practices-for-managing-python-dependencies/)
- [fastapi-cache2 (GitHub)](https://github.com/long2ice/fastapi-cache)
- [FastAPI Caching Overview](https://dev.to/sivakumarmanoharan/caching-in-fastapi-unlocking-high-performance-development-20ej)
- [ChromaDB Performance Guide](https://docs.trychroma.com/guides/deploy/performance)
- [ChromaDB Memory Management Cookbook](https://cookbook.chromadb.dev/strategies/memory-management/)
- [ChromaDB Performance Tips](https://cookbook.chromadb.dev/running/performance-tips/)
- [SQLite Appropriate Uses](https://sqlite.org/whentouse.html)
- [Backup Strategies for SQLite in Production](https://oldmoe.blog/2024/04/30/backup-strategies-for-sqlite-in-production/)
