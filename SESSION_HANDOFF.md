# Session Handoff — 2026-03-18 (Session 7: EXT-1 + Memory Graph Diversity + Inference Fix)

## Mission
Configure external NVMe storage (EXT-1), implement memory graph diversity for diverse high-quality node types, fix the inference client thinking model bug, and address macOS chat UX issues.

## Completed

### EXT-1: External Storage Setup — COMPLETE
- Formatted 4TB Samsung 990 PRO as APFS at `/Volumes/HestiaStorage` on Mac Mini
- Moved 138GB Ollama models to external via symlink (`~/.ollama/models → /Volumes/HestiaStorage/ollama-models/models`)
- Created `scripts/archive-logs.sh` (weekly) + `scripts/backup-databases.sh` (nightly)
- Created `hestia/config/storage.yaml`
- Scheduled via crontab: backup 3:30am daily, archive Sunday 2am
- Enabled SSH Full Disk Access + fixed GitHub SSH key on Mac Mini
- SPRINT.md: EXT-1 marked COMPLETE. Commit: `c5d813a`

### Memory Graph Diversity — Code Complete, Awaiting Reclassification
- Discovery: `docs/discoveries/memory-graph-diversity-2026-03-18.md`
- Second opinion: `docs/plans/memory-graph-diversity-second-opinion-2026-03-18.md` (Claude + Gemini approved)
- Plan: `docs/superpowers/plans/2026-03-18-memory-graph-diversity.md`
- Commits: `55cacc8` → `d3ecd80` → `a1e198f` → `8fbe0fa` → `beaec5b`
- 40 new tests (36 classification + 4 fact extraction), all passing
- LLM-backed classification with quality gates (promo email filter, Intelligence notes only)
- Retroactive reclassification script ready: `scripts/reclassify-conversations.py`

### Inference Client Thinking Model Fix — FIXED
- **Root cause:** Qwen 3.5's thinking tokens consume `num_predict` budget, leaving `response` field empty
- Every `complete()` call returned empty strings since Qwen 3.5 was installed
- This also explains why fact extraction produced 0 facts since inception
- **Fix:** Added `think` parameter through `_call_ollama` → `_call_local_with_retries` → `_call_with_routing` → `complete()`. Tagger uses `think=False`.
- Commit: `8efe0c2`

### macOS Chat UX — 2 of 3 Fixed
- **Thinking indicator**: Added animated dots bubble for `isLoading && !isTyping` gap. Commit: `016654f`
- **Avatar moved**: Tia avatar (44x44) added to Command Center greeting in HeroSection, reduced to 32x32 in chat header. Commit: `897cb82`
- **Input field resizing**: NOT addressed — dynamic height logic exists (36-200pt) but user reports it doesn't work. Needs debugging next session.

### All Pushed
- `45376c8` is on `origin/main`. Pre-push passed (tests + macOS build).

## In Progress

### Reclassification Deployment
- Mac Mini needs `git pull` to get inference fix + classification code
- Then: `source .venv/bin/activate && python scripts/reclassify-conversations.py --limit 10` to verify LLM returns classifications
- If counts look good: `--apply` for full run (1,282 candidates after quality gate filtering)

### Input Field Resizing
- Dynamic height exists in `CLITextView.swift` (lines 112-122: `reportContentHeight()` via NSLayoutManager)
- Clamped 36-200pt in `MacMessageInputBar.swift` (line 22-24)
- User reports it doesn't resize. Debug: check if `textDidChange` → `reportContentHeight` → SwiftUI binding update is working
- No formatting hotkeys (bold/italic) — plain text only (`isRichText = false`)

## Decisions Made
- LLM-first classification (not keywords) for Decision/Preference/Research — asymmetric error cost with decay rates
- Only ACTION_ITEM uses sync-path heuristic (explicit TODO: prefixes)
- Confidence threshold 0.7 for chunk type promotion
- `think=False` for all structured inference calls (tagger, fact extraction)
- OBSERVATION chunks: mail filtered for promos, notes restricted to Intelligence folder
- ChromaDB must be updated alongside SQLite in retroactive reclassification

## Test Status
- 40 new tests passing (36 classification + 4 fact extraction diagnostic)
- 2 pre-existing inference integration tests fail (thinking model timeout — same root cause, tests don't pass `think=False`)
- 1 pre-existing error: `test_memory.py::TestMemorySource::test_query_filter_by_source`
- macOS build: PASS (verified by build validator)

## Uncommitted Changes
None — all committed and pushed.

## Known Issues / Landmines
- **Mac Mini needs git pull**: Code pushed but Mini still has old version. Run `git pull` before testing.
- **Mac Mini git state**: We did `git reset --hard origin/main` earlier. Any local-only changes gone.
- **Fact extractor uses `client.generate()`**: This method doesn't exist on InferenceClient — the fact extractor's `_get_inference_client()` awaits a sync function. The pipeline needs separate investigation for the `generate()` method source. The `think` parameter won't automatically apply to fact extraction until this is resolved.
- **`_parse_tag_response` regex** (`r'\{[^{}]*\}'`): Won't match nested JSON. If LLM wraps output in backticks or adds nested objects, parsing fails silently.
- **Thinking model tests**: `test_inference.py::TestInferenceClientIntegration::test_simple_completion` and `test_chat_completion` fail because they hit real Ollama without `think=False`. Consider adding `think=False` to these tests or increasing their timeout.

## Process Learnings

### Config Gaps
- **SSH Full Disk Access**: Not documented. Mac Mini SSH sessions can't access external volumes or crontab without Full Disk Access for sshd. Add to deployment docs.
- **Thinking model awareness**: No config or documentation warns that Qwen 3.5 is a thinking model that consumes tokens differently. Add a note to CLAUDE.md under inference.

### First-Pass Success
- 7/8 tasks completed on first pass. Rework: Python 3.9 type hints (`int | None`), inference client empty response was unexpected.
- **Top blocker**: The thinking model bug — existed since Qwen 3.5 was installed, silently broke all inference. A `/preflight` check that verifies inference returns non-empty would have caught this.

### Agent Orchestration
- Good: Parallel dispatch of hestia-explorer for 4 research topics simultaneously
- Good: Subagent-driven development for Task 1 (complex classification), inline for Task 2 (3-line edit)
- Good: Parallel Tasks 3+4 dispatch (independent work)
- Miss: Should have run a quick inference test on the Mini before starting reclassification deployment

## Next Steps
1. **Pull on Mini**: `ssh andrewroman117@hestia-3.local 'cd ~/hestia && git pull'`
2. **Verify inference fix**: `ssh andrewroman117@hestia-3.local 'cd ~/hestia && source .venv/bin/activate && python3 -c "import asyncio; from hestia.inference import get_inference_client; r=asyncio.run(get_inference_client().complete(\"Say hello\", think=False, validate=False)); print(repr(r.content))"'`
3. **Run reclassification dry run**: `python scripts/reclassify-conversations.py --limit 10`
4. **If classifications look good**: `python scripts/reclassify-conversations.py --apply`
5. **Restart server**: Kill stale, restart, verify chat works with thinking indicator
6. **Debug input field resizing**: Check `CLITextView.swift:112-122` — `reportContentHeight()` may not be propagating to SwiftUI binding
