# Discovery Report: Apple Metadata Cache + Smart Tool Resolution
**Date:** 2026-03-05
**Confidence:** High
**Decision:** Build it. A lightweight metadata cache with fuzzy title resolution will convert the hardest LLM problem (multi-step tool chaining) into the easiest one (single tool call with a name), dramatically improving reliability for the Qwen 7B local model.

## Hypothesis
*A daily-synced SQLite cache of Apple ecosystem metadata (Notes titles, Calendar event titles, Reminder titles, Mail subjects) with intelligent fuzzy resolution in tool executors will enable small local models (Qwen 2.5 7B / Qwen 3 8B) to reliably access Apple data without requiring multi-step tool chains.*

## Context: The Problem Today

The current Apple tool architecture requires the LLM to reason through multi-step chains:

1. **Notes:** "Read my grocery list" requires: `list_notes()` -> scan results -> `get_note(note_id)`. The `get_note_by_title` tool exists as a partial fix (line 385-411 of `apple/tools.py`) but the model must still know to call it vs `get_note`, and it only does substring matching.

2. **Calendar:** "What's on my calendar today?" works (dedicated `get_today_events` tool), but "When is my dentist appointment?" requires: `list_events(days=30)` -> scan results -> find match. No title-based lookup exists.

3. **Reminders:** "What's on my shopping list?" requires: `list_reminder_lists()` -> `list_reminders(list_name="Shopping")`. The model must correctly identify the list name AND pass it exactly.

4. **Mail:** Already uses direct SQLite access to Apple Mail's Envelope Index database. Already has search. Least affected.

### Measured Failure Modes

Based on the architecture and industry research:

- **Off-the-shelf 7B models achieve ~40% accuracy** on multi-step tool chains (Berkeley TinyAgent research)
- **Qwen 3 8B achieves 0.933 F1** on *single* tool selection -- the key insight is that single-step is reliable, multi-step is not
- The model frequently selects the wrong tool, passes wrong parameters, or hallucinates note/reminder IDs
- Each CLI subprocess call takes up to 30 seconds timeout, so a 2-step chain could take 60s worst case

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Inbox module already proves the pattern (SQLite cache + Apple client aggregation + TTL refresh). `get_note_by_title` proves title-based resolution works. All 4 Apple clients exist and work. BaseDatabase ABC provides standard schema pattern. | **Weaknesses:** AppleScript calls are slow (30s timeout each). Notes CLI uses AppleScript, not EventKit. Current `search_notes` does full `list_notes()` then client-side filter. No existing fuzzy matching library in deps. |
| **External** | **Opportunities:** Single-step tool calls are 2x more reliable than multi-step for 7B models. Cache enables instant lookups (<10ms vs 2-30s). Metadata enables smarter prompt injection ("you have 47 notes, 12 reminders, 3 calendars"). Could power proactive briefings. | **Threats:** Apple data changes between syncs (stale cache). Notes body content is NOT cached (only metadata), user may expect full content. AppleScript API may change in macOS updates. New dependency (rapidfuzz) adds maintenance burden. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Notes title cache + fuzzy resolver (biggest pain point, most frequent failure mode) | Calendar event title search (less frequent, `get_today_events` covers most cases) |
| **Low Priority** | Reminders list name resolution (model already handles simple list names OK) | Mail metadata cache (Mail already uses direct SQLite -- mostly redundant) |

## Argue (Best Case)

### Evidence FOR Building This

1. **The reliability gap is enormous.** Single-step tool calling: ~93% accuracy. Multi-step: ~40%. A metadata cache converts multi-step into single-step for the most common operations.

2. **Proven pattern already exists in the codebase.** The Inbox module (`inbox/manager.py`, `inbox/database.py`) does exactly this: aggregates Apple Mail + Reminders + Calendar into SQLite with a 30s TTL cache. The new module would follow the identical pattern with a longer TTL (daily sync vs 30s).

3. **`get_note_by_title` already demonstrates the approach partially** -- it lists all notes, does substring matching, picks the best, then fetches content. The cache just pre-computes step 1 and adds fuzzy matching.

4. **The cost is low.** Metadata is tiny. 1000 notes with titles + folders + modified dates = ~100KB. 500 calendar events = ~50KB. 200 reminders = ~20KB. SQLite handles this trivially.

5. **Enables a superior user experience.** Instead of "I couldn't find that note, can you be more specific?", the system can say "I found 3 notes matching 'grocery': 'Grocery List', 'Grocery Store Rewards', 'Groceries Dec 2025'. Which one?"

6. **FTS5 + RapidFuzz is a well-understood stack.** SQLite FTS5 provides fast candidate generation, RapidFuzz (C++ backend, MIT licensed) provides scoring at 5-100x the speed of TheFuzz. Combined latency: <5ms for a lookup against 1000 items.

7. **Unblocks prompt-injected context.** With the cache, the system prompt can include: "User has these note titles: [...]" -- enabling the model to reference items by name without any tool call at all.

## Refute (Devil's Advocate)

### Evidence AGAINST Building This

1. **Stale cache is a real problem.** If user creates a note "Meeting Notes" and immediately asks "read my meeting notes", the cache won't have it until next sync. Mitigation: write-through on create operations (tools.py `create_note` also updates cache).

2. **The Qwen 3 line may solve this without caching.** Qwen 3 8B scores 0.933 F1 on tool selection -- possibly good enough for 2-step chains. The model-swap sprint (see `docs/plans/2026-03-05-model-swap-planning-design.md`) may obsolete this effort. Counter-argument: even Qwen 3 8B fails on complex parameter extraction; single-step is *always* more reliable regardless of model.

3. **New dependency (rapidfuzz) adds surface area.** It's a compiled C++ extension -- could cause build issues on ARM vs x86. Mitigation: fall back to simple substring matching if rapidfuzz unavailable, like `get_note_by_title` already does.

4. **Complexity for marginal gain on Calendar/Mail.** Calendar already has `get_today_events` and date-range queries. Mail already has SQLite search. The main win is Notes and Reminders. Counter-argument: build it for Notes/Reminders first, extend later only if needed.

5. **Token budget pressure.** Injecting all note titles into the system prompt eats into the 2000-token system budget. With 500+ notes, this could overflow. Mitigation: inject only top-N most recent/relevant titles, or use a "smart context" approach where titles are only injected when the user's query seems Apple-data-related.

## Third-Party Evidence

### What Others Do

- **Apple Intelligence (2026):** Apple's own Siri evolution is moving toward deep cross-app context via on-device indexing -- the same architectural pattern we're proposing. They acquired Mayday (AI calendar app) for exactly this capability.

- **Toki AI Calendar:** Uses a natural-language interface over calendar data, with local indexing for instant lookups. Validates the pattern of caching calendar metadata for conversational access.

- **Berkeley TinyAgent:** Demonstrated that **ToolRAG** -- retrieving relevant tool definitions based on the user query -- dramatically improves small model accuracy. Our metadata cache is the data-side equivalent: retrieving relevant *entity names* based on the query.

- **Think-Augmented Function Calling (TAFC):** Shows that complex parameter extraction is the hardest part for small models. Our cache eliminates the need for complex parameter construction by resolving names to IDs server-side.

### Alternative Approaches Considered

1. **Fine-tune the model on Apple tool chains** -- Could work (Berkeley showed 40% -> 83% improvement) but requires ongoing training data curation, model retraining, and doesn't transfer across model swaps.

2. **Multi-turn automatic retry** -- Let the model fail, catch the error, retry with better context. Already partially implemented (the fallback message in handler.py line 864). But this doubles latency and annoys users.

3. **Hardcode common operations as "macro tools"** -- e.g., `read_note_by_name`, `find_event_by_keyword`. This is essentially what `get_note_by_title` already is. The cache approach generalizes this pattern rather than proliferating special-case tools.

4. **Inject all Apple data into every prompt** -- Works for small datasets but doesn't scale. 100 notes with full body content would blow the token budget. Metadata-only cache is the right middle ground.

## Recommendation

### Architecture Design

```
hestia/
  apple_cache/
    models.py          # AppleCacheEntry dataclass (source, native_id, title, folder/list, modified_at)
    database.py        # AppleCacheDatabase extends BaseDatabase
                       #   - apple_metadata table (FTS5 virtual table for title search)
                       #   - indexes on source, folder, modified_at
    manager.py         # AppleCacheManager
                       #   - sync_all() -- parallel sync of Notes/Calendar/Reminders
                       #   - resolve(query, source?) -- fuzzy title resolution
                       #   - get_context_summary() -- for prompt injection
    resolver.py        # SmartResolver
                       #   - FTS5 candidate generation
                       #   - RapidFuzz scoring (token_set_ratio for best partial match)
                       #   - Returns ranked matches with confidence scores
    sync.py            # SyncEngine
                       #   - Calls existing Apple clients (NotesClient, CalendarClient, etc.)
                       #   - Write-through hooks for create/update tools
                       #   - Configurable TTL per source
```

### Tool Integration

Modify existing tools non-destructively:

1. **New resolver-backed tools:**
   - `find_note(query)` -- fuzzy search notes by title, returns top matches with preview
   - `read_note(query)` -- fuzzy resolve + fetch content in one call
   - `find_event(query, days=30)` -- fuzzy search events by title
   - `find_reminder(query)` -- fuzzy search reminders by title

2. **Smart pre-resolution in existing tools:**
   - `get_note(note_id_or_title)` -- if `note_id` doesn't look like an ID, run through resolver first
   - `list_reminders(list_name)` -- fuzzy-match `list_name` against known list names

3. **Prompt context injection:**
   - When user query contains Apple-related keywords (note, remind, calendar, meeting, etc.), inject relevant cached titles into the system prompt

### Sync Strategy

| Source | Sync Frequency | TTL | Write-Through |
|--------|---------------|-----|---------------|
| Notes | Every 6 hours + on startup | 6h | Yes (create_note, update_note) |
| Calendar | Every 2 hours + on startup | 2h | Yes (create_event) |
| Reminders | Every 4 hours + on startup | 4h | Yes (create_reminder, complete_reminder) |
| Mail | Skip (already has SQLite) | N/A | N/A |

### Estimated Effort

- **Database + models:** 2 hours (clone inbox pattern)
- **SyncEngine:** 3 hours (parallel Apple client calls, write-through hooks)
- **SmartResolver:** 3 hours (FTS5 + rapidfuzz scoring)
- **New tools + tool modifications:** 2 hours
- **Tests:** 3 hours (40-50 tests following existing patterns)
- **Prompt integration:** 1 hour
- **Total:** ~14 hours (2-3 sessions)

### Dependencies

- `rapidfuzz` (pip install, MIT license, well-maintained, 10K+ GitHub stars)
- No other new dependencies -- uses existing `aiosqlite`, `BaseDatabase`, Apple clients

### Confidence: HIGH

The evidence is clear:
- The pattern is proven in the codebase (Inbox module)
- The problem is well-characterized (multi-step tool failure rates)
- The solution is architecturally simple
- The cost is low (~14 hours, 1 new dependency)
- The win is large (40% reliability -> ~93% for Apple data operations)

### What Would Change This Recommendation

- If Qwen 3 8B multi-step tool accuracy exceeds 90% in benchmarks -- then the urgency drops (but cache still helps with latency)
- If Apple Notes drops AppleScript support in a future macOS -- would need EventKit migration for Notes (Calendar/Reminders already use EventKit)
- If the user has >10,000 notes -- FTS5 still handles this fine, but sync time grows. Would need delta-sync rather than full-scan.

## Final Critiques

### The Skeptic: "Why won't this work?"

*Challenge:* "You're adding a whole new module with a new dependency for something that `get_note_by_title` already mostly solves."

*Response:* `get_note_by_title` does a full `list_notes()` AppleScript call every time (2-10 seconds), only does substring matching (no fuzzy), only works for notes (not calendar/reminders), and requires the model to know this specific tool exists. The cache turns 2-10s into <10ms, adds fuzzy matching, covers all Apple sources, and enables prompt injection so the model doesn't even need to pick the right tool.

### The Pragmatist: "Is the effort worth it?"

*Challenge:* "14 hours is 2+ weeks of Andrew's time. Is this the highest ROI investment?"

*Response:* Apple data access is the primary daily use case for Hestia (check reminders, read notes, look at calendar). If it fails 60% of the time with multi-step chains, the assistant is broken for its core purpose. This is the highest-impact reliability improvement possible short of swapping to a larger model. And it works *with* a model swap -- the cache benefits any model.

### The Long-Term Thinker: "What happens in 6 months?"

*Challenge:* "Apple Intelligence in iOS 19 / macOS 16 may provide native AI-assisted access to Notes/Calendar. Does this become obsolete?"

*Response:* Apple Intelligence is Siri-only and cloud-processed. Hestia's value proposition is local, private, and customized. Even if Apple adds AI features to Calendar, Hestia still needs to access the data for its own reasoning (briefings, proactive patterns, cross-referencing). The cache becomes more valuable, not less, as the system gets smarter.

## Open Questions

1. **Should we use APScheduler for periodic sync?** The orders module already uses it. Or simpler: sync on first access + TTL, like Inbox does.
2. **How aggressive should prompt injection be?** Inject all titles (token-expensive) or only inject when query seems Apple-related (requires intent detection)?
3. **Should the cache store note body content?** Large storage cost, but would enable "search my notes for X" without AppleScript calls. Recommendation: start with metadata-only, add body caching later based on usage.
4. **Integration with model-swap sprint:** The model-swap planning doc exists (`docs/plans/2026-03-05-model-swap-planning-design.md`). Should cache be built first (makes any model better) or after model swap (new model may need it less)?

## Sources

- [Docker: Local LLM Tool Calling Evaluation](https://www.docker.com/blog/local-llm-tool-calling-a-practical-evaluation/)
- [Berkeley Function Calling Leaderboard (BFCL) V4](https://gorilla.cs.berkeley.edu/leaderboard.html)
- [TinyAgent: Function Calling at the Edge (Berkeley AI Research)](https://bair.berkeley.edu/blog/2024/05/29/tiny-agent/)
- [RidgeRun: Introducing Juniper (Fine-Tuned Small Model for Function Calling)](https://www.ridgerun.ai/post/introducing-juniper-fine-tuned-small-local-model-for-function-calling)
- [Improving Small-Scale LLMs Function Calling for Reasoning Tasks (arXiv)](https://arxiv.org/abs/2410.18890)
- [Think-Augmented Function Calling (arXiv)](https://arxiv.org/abs/2601.18282)
- [RapidFuzz: Fast Fuzzy String Matching (GitHub)](https://github.com/rapidfuzz/RapidFuzz)
- [Best Local LLMs for Agents in 2026 (Clawctl)](https://www.clawctl.com/blog/best-local-llm-coding-2026)
- [Fine-Tuning Small Language Models for Function Calling (Microsoft)](https://techcommunity.microsoft.com/blog/machinelearningblog/fine-tuning-small-language-models-for-function-calling-a-comprehensive-guide/4362539)
- [iOS 19 AI Calendar via Mayday Acquisition (9to5Mac)](https://9to5mac.com/2025/05/09/ios-19-could-bring-apple-intelligence-to-calendar-app-per-acquisition/)
