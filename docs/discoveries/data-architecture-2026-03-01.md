# Discovery Report: Hestia Data Architecture

**Date:** 2026-03-01
**Confidence:** High
**Decision:** Keep the multi-database architecture. Fix the six concrete issues identified below. Do not consolidate into a single database.

## Hypothesis

*"Is Hestia's data architecture -- 10 separate SQLite databases + 1 ChromaDB instance + markdown files + macOS Keychain -- well-designed for its current and future needs, or does it need restructuring?"*

### Success Criteria
A good answer identifies whether the current architecture is (a) sound and should be kept with minor fixes, (b) fundamentally flawed and needs restructuring, or (c) fine now but heading toward a cliff.

### Decision Context
Hestia is a single-user personal AI assistant on Mac Mini M1 with ~1,100 tests, 116 API endpoints, and 21 backend modules. It has been built iteratively over 15 sessions. The data layer was never designed holistically -- it grew module by module. This research asks whether that organic growth created any structural debt worth addressing.

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Clean module isolation, consistent patterns (`database.py` + `manager.py` + singleton factory), async throughout, good indexing, foreign keys enabled, ChromaDB handles vector search well | **Weaknesses:** No unified migration framework, path inconsistency (8 DBs use `Path.home()`, 2 use relative `Path("data")`), no backup story, ChromaDB causes test hangs, only 1/10 databases has `user_id` scoping |
| **External** | **Opportunities:** sqlite-vec could replace ChromaDB (eliminates hang + reduces dependencies), the "SQLite per module" pattern is industry-validated (Litestack, NanoClaw), total data is only 2MB | **Threats:** Multi-user readiness gap contradicts project rules (`multi-user.md`), no disaster recovery path, schema drift risk as modules evolve independently |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | P1: Fix path inconsistency (newsfeed + explorer use relative paths) | P4: Add schema_version tables to databases that lack them (6/10 missing) |
| | P2: Evaluate replacing ChromaDB with sqlite-vec (eliminates test hang, reduces dependencies) | P5: Standardize `close_X_database()` pattern (4/10 missing explicit close functions) |
| **Low Priority** | P3: Add `user_id` columns to remaining databases (future multi-user readiness) | P6: Create backup/export script for all 10 databases |

---

## Argue (Best Case)

The multi-database architecture is **correct for Hestia's workload**. Here is the evidence:

1. **Module isolation is a feature, not a bug.** Each database file can be backed up, restored, or wiped independently. Corruption in `wiki.db` doesn't affect `memory.db`. This is particularly valuable for a personal AI system where experimentation is frequent.

2. **Write concurrency is genuinely improved.** SQLite's single-writer limitation means that if chat (memory.db), health sync (health.db), and wiki generation (wiki.db) all write simultaneously, they'd block each other in a single database. With separate files, they write in parallel.

3. **The data IS logically independent.** Looking at cross-module references:
   - Only `newsfeed/manager.py` reaches across modules (aggregating from orders, memory, tasks, health) -- and it does this through manager APIs, not cross-database joins.
   - No other module imports another module's database layer.
   - There are zero foreign keys spanning databases.

4. **The pattern is industry-validated.** The Litestack framework (popular in Ruby/SQLite world) recommends exactly this pattern -- separate database files per service. NanoClaw, Stevens, and Turso's agent model all validate the "SQLite per concern" approach.

5. **Total footprint is trivial.** All 10 databases + ChromaDB = 2.0MB. Connection overhead for 10 async connections is negligible on a 16GB M1.

6. **The consistent internal API surface is clean:**
   - Every module: `models.py` -> `database.py` -> `manager.py`
   - Every database: singleton factory via `get_X_database()`
   - Every database: `aiosqlite`, `Row` factory, foreign keys enabled
   - This makes the system predictable and auditable.

---

## Refute (Devil's Advocate)

The architecture has **real issues that will bite eventually**:

1. **Path inconsistency is a latent bug.** 8 databases use `Path.home() / "hestia" / "data"` (absolute, home-based). 2 databases (`newsfeed`, `explorer`) use `Path("data")` (relative to CWD). If the server is started from a different directory, those 2 databases will silently create/read from wrong locations. This is a deployment footgun.

2. **No migration framework.** Each database handles schema changes ad-hoc:
   - `memory.db` and `tasks.db`: have `schema_version` tables (but version is still 1)
   - `wiki.db` and `invites.db`: use `PRAGMA table_info()` to detect missing columns, then `ALTER TABLE`
   - `cloud.db`, `health.db`, `orders.db`, `agents.db`, `user.db`, `explorer.db`, `newsfeed.db`: no migration support at all -- schemas are `CREATE TABLE IF NOT EXISTS` only

   This means: if you need to add a column to `health_metrics`, you either add it with `ALTER TABLE` and hope, or drop and recreate the table. There is no rollback, no version tracking, no migration chain.

3. **The multi-user readiness gap is real.** The `.claude/rules/multi-user.md` file says "Include `user_id` scoping on all new database tables." But only `newsfeed_state` has `user_id`. The `memory_chunks`, `sessions`, `background_tasks`, `orders`, `health_metrics`, `wiki_articles`, `agent_profiles`, `user_profiles`, and `drafts` tables are all single-user by design. If Hestia ever needs a second user (e.g., a family member), it requires schema changes to 15+ tables across 9 databases.

4. **ChromaDB is the weakest link.** It:
   - Spawns non-daemon background threads that cause pytest to hang (requiring `os._exit()` hack)
   - Adds a heavy dependency (~50MB with transitive deps)
   - Uses SQLite internally anyway (`chroma.sqlite3` = 1MB)
   - Stores only 124 vectors (matching `memory_chunks` rows)
   - Could be replaced by `sqlite-vec` extension in `memory.db` itself

5. **No backup or disaster recovery.** There is no script to back up all 10 databases + ChromaDB + markdown user files + Keychain credentials. The `deploy-to-mini.sh` rsyncs code but not data. A disk failure on Mac Mini means total data loss.

6. **10 singleton connections are 10 points of failure.** Each database has its own connection lifecycle. If any singleton is initialized in the wrong order, or fails to connect, the server may partially start with some modules working and others silently broken. The `lifespan()` function initializes 12 managers sequentially -- any failure cascades.

---

## Third-Party Evidence

### Validates the multi-DB approach:
- **Litestack** (production Rails + SQLite framework) explicitly recommends one database per service for write concurrency. [Source: fractaledmind.com]
- **SQLite forum** (Richard Hipp et al.) consensus: "For device-local storage with low writer concurrency, separate databases per concern is fine." The ATTACH mechanism exists specifically for this pattern.
- **NanoClaw** (2026): Minimal AI assistant uses per-group-chat SQLite databases for isolation.
- **Stevens** (2025): Single-table approach works for simple assistants but wouldn't scale to Hestia's complexity (21 modules, 116 endpoints).

### Challenges the ChromaDB choice:
- **sqlite-vec** (Mozilla Builders project, 2024-2026): Pure C, zero dependencies, runs everywhere SQLite runs. Designed specifically for local-first AI applications. Integrated with LangChain. Would eliminate ChromaDB entirely.
- ChromaDB "incidentally uses SQLite under the hood" -- so Hestia currently has SQLite storing metadata, then ChromaDB wrapping another SQLite to store vectors of the same data. That's redundant.

### Contradicts full consolidation:
- SQLite's single-writer lock means consolidation would reduce write throughput.
- The Xojo forum, ThinkGeo community, and SQLite official forum all conclude: "Don't consolidate unless you need cross-table joins."

---

## Recommendation

**Keep the multi-database architecture. Execute six targeted fixes.**

### Fix 1 (Critical): Path Consistency
Change `newsfeed/database.py` and `explorer/database.py` to use `Path.home() / "hestia" / "data"` like all other databases. The relative `Path("data")` is a deployment bug waiting to happen.

**Effort:** 30 minutes. **Risk:** Low (just change default path, existing data stays where it is).

### Fix 2 (High): Evaluate sqlite-vec to Replace ChromaDB
ChromaDB adds a heavy dependency, causes test hangs, and wraps SQLite internally. `sqlite-vec` would:
- Eliminate the `conftest.py` `os._exit()` hack
- Reduce dependencies by ~50MB
- Keep vectors in `memory.db` alongside metadata (atomic operations)
- Use the all-MiniLM-L6-v2 model can still be used via sentence-transformers for embedding generation

**Effort:** 2-3 hours (spike). **Risk:** Medium (need to verify embedding compatibility, query performance). **Recommendation:** Spike it in a branch. If performance is comparable, migrate.

### Fix 3 (Medium): Add Lightweight Migration Framework
Create a shared `hestia/database/migrator.py` that:
- Reads `schema_version` from each database
- Applies numbered migration functions in order
- Logs what was applied
- No external deps (pure aiosqlite)

This replaces the ad-hoc `PRAGMA table_info()` + `ALTER TABLE` pattern.

**Effort:** 2-3 hours. **Risk:** Low.

### Fix 4 (Medium): Standardize Schema Version Tables
Add `schema_version` to the 6 databases that lack it (cloud, health, orders, agents, user, wiki, explorer, newsfeed). Sets the foundation for Fix 3.

**Effort:** 1 hour. **Risk:** Trivial.

### Fix 5 (Low): Create Backup Script
`scripts/backup-data.sh` that:
- Copies all `.db` files from `~/hestia/data/`
- Copies `data/chromadb/`
- Copies `data/user/` (markdown profiles)
- Copies `data/agents/` (v2 configs)
- Timestamps the backup
- Optionally rsyncs to an external location

**Effort:** 1 hour. **Risk:** None.

### Fix 6 (Low/Deferred): User ID Scoping
Not needed now (single-user system). When multi-user becomes a real requirement:
- Add `user_id TEXT` column to all user-scoped tables
- Default to `"user-default"` for migration
- Filter by `user_id` from JWT claims in all queries

**Effort:** 4-6 hours when needed. **Risk:** Defer is fine -- premature optimization.

### Confidence Level
**High.** The evidence from codebase analysis, industry patterns, and quantitative data (2MB total, 124 vectors, 10 DBs, 0 cross-DB joins) all point the same direction. The multi-DB pattern is correct. The issues are hygiene, not architecture.

### What Would Change This Recommendation
- If Hestia needed cross-database ACID transactions (currently: no module needs this)
- If data volume grew past 1GB total (currently: 2MB, 10,000x headroom)
- If a second user was imminent (would require Fix 6 urgently)
- If sqlite-vec spike reveals it can't match ChromaDB query quality (unlikely but possible)

---

## Final Critiques

### The Skeptic: "Why won't this work?"

**Challenge:** "10 separate databases means 10 connection pools, 10 initialization paths, 10 shutdown paths. That's 10x the surface area for bugs."

**Response:** True, but mitigated by the consistent pattern. Every database follows the same template: `__init__` -> `connect()` -> `_init_schema()` -> singleton factory. The `lifespan()` function initializes all of them in one place. In 15 sessions of development, zero bugs have been attributed to multi-database connection management. The pattern is boilerplate-heavy but reliable.

### The Pragmatist: "Is the effort worth it?"

**Challenge:** "You're recommending 6 fixes for an architecture that works. Andrew has 6 hours/week. Is this the best use of his time?"

**Response:** Fix 1 (paths) is 30 minutes and prevents a real deployment bug. Fix 5 (backup) is 1 hour and prevents data loss. Those two alone justify the research. Fix 2 (sqlite-vec) is optional but high-value if the ChromaDB test hang continues to be a friction point. Fixes 3-4 (migrations) are important but can be batched into a single session. Fix 6 (user_id) is explicitly deferred.

**Priority order:** Fix 1 > Fix 5 > Fix 2 > Fix 4 > Fix 3 > Fix 6.

### The Long-Term Thinker: "What happens in 6 months?"

**Challenge:** "Hestia is growing. 21 modules today, maybe 30 in 6 months. Does this architecture scale to 15 databases?"

**Response:** Yes, with caveats. The pattern scales linearly -- each new module gets its own database, same template. The risk is not technical but cognitive: can a developer hold 15 databases in their head? The answer is yes, because they're isolated -- you only need to think about the database for the module you're working on. The `newsfeed/manager.py` cross-module aggregation pattern scales too, because it reads through manager APIs, not cross-database queries.

The real 6-month risk is the migration story. Without Fix 3, each new column addition is a one-off hack. After 30 modules with 3 migrations each, that's 90 ad-hoc `ALTER TABLE` statements with no rollback capability. The migration framework (Fix 3) is the most important long-term investment.

---

## Architecture Summary

### Current Data Stores (12 total)

| Store | Technology | Path | Size | Rows | Purpose |
|-------|-----------|------|------|------|---------|
| memory.db | SQLite | ~/hestia/data/ | 264KB | 124 chunks, 537 tags, 9 sessions | Conversation memory metadata |
| ChromaDB | ChromaDB (SQLite) | ~/hestia/data/chromadb/ | 1.2MB | 124 vectors | Semantic search embeddings |
| wiki.db | SQLite | ~/hestia/data/ | 192KB | 60 articles | AI-generated documentation |
| cloud.db | SQLite | ~/hestia/data/ | 44KB | 1 provider, 60 usage records | Cloud LLM config + usage |
| health.db | SQLite | ~/hestia/data/ | 44KB | 0 (unused) | HealthKit metrics |
| orders.db | SQLite | ~/hestia/data/ | 40KB | 0 (unused) | Scheduled prompts |
| agents.db | SQLite | ~/hestia/data/ | 36KB | 3 profiles | Agent personas (Tia/Mira/Olly) |
| tasks.db | SQLite | ~/hestia/data/ | 32KB | 0 (unused) | Background tasks |
| newsfeed.db | SQLite | **data/** (relative!) | 32KB | 1 item | Timeline cache |
| invites.db | SQLite | ~/hestia/data/ | 28KB | 20 devices | QR onboarding + device registry |
| user.db | SQLite | ~/hestia/data/ | 28KB | 1 profile | User settings |
| explorer.db | SQLite | **data/** (relative!) | 20KB | 0 (unused) | Drafts + resource cache |
| data/user/ | Markdown | ~/hestia/data/user/ | ~3KB | 8 files | Identity profiles (MIND, BODY, etc.) |
| data/agents/ | Markdown + YAML | ~/hestia/data/agents/ | ~5KB | 3 dirs | Agent v2 configs (.md-based) |
| Keychain | macOS Keychain | System | N/A | ~5 keys | API keys, JWT secret, master key |

### Cross-Module Data Flow

```
                    +-----------+
                    |  Newsfeed |
                    |  Manager  |
                    +-----+-----+
                          |
            reads via manager APIs (NOT cross-DB joins)
            |         |         |         |
       +----+    +----+    +---+    +----+
       |Orders|  |Memory|  |Tasks| |Health|
       +------+  +------+  +-----+ +------+

All other modules: self-contained (database.py <-> manager.py only)
```

---

## Open Questions

1. **sqlite-vec embedding compatibility:** Does sqlite-vec support cosine similarity with the same quality as ChromaDB's HNSW? Needs a spike.
2. **ChromaDB data migration:** If replacing ChromaDB, do we re-embed all 124 chunks or export/import the existing vectors?
3. **Backup destination:** Where should backups go? iCloud Drive? External volume? Another Tailscale node?
4. **Health data volume projection:** HealthKit sync could generate thousands of metrics/day. Is `health.db` indexed well enough for 100K+ rows? (Current answer: yes, the indexes are on the right columns.)

---

## Sources

- [Stevens: AI assistant with single SQLite table](https://www.geoffreylitt.com/2025/04/12/how-i-made-a-useful-ai-assistant-with-one-sqlite-table-and-a-handful-of-cron-jobs)
- [NanoClaw: 500 Lines vs 50 Modules](https://fumics.in/posts/2026-02-02-nanoclaw-agent-architecture)
- [The SQLite Renaissance (2026)](https://dev.to/pockit_tools/the-sqlite-renaissance-why-the-worlds-most-deployed-database-is-taking-over-production-in-2026-3jcc)
- [sqlite-vec: Vector search SQLite extension](https://github.com/asg017/sqlite-vec)
- [SQLite-Vec Mozilla Builders](https://builders.mozilla.org/project/sqlite-vec/)
- [SQLite vs ChromaDB comparison](https://dev.to/stephenc222/sqlite-vs-chroma-a-comparative-analysis-for-managing-vector-embeddings-4i76)
- [SQLite Quick Tip: Multiple Databases](https://fractaledmind.com/2024/01/02/sqlite-quick-tip-multiple-databases/)
- [SQLite Forum: Breaking up into multiple databases](https://sqlite.org/forum/info/bb6d44adb8690c4c5cb2ac397c7ac5d4d53abc2d9cff1873b7ea48058713a618)
- [Turso: Databases for the agentic era](https://turso.tech/)
- [Appropriate Uses for SQLite](https://sqlite.org/whentouse.html)
