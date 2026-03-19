# Session Handoff — 2026-03-18 (Session 7: EXT-1 + Memory Graph Diversity)

## Mission
Configure external NVMe storage tier (EXT-1), implement memory graph diversity so the Research graph shows diverse high-quality node types, and fix the inference client thinking model bug.

## Completed

### EXT-1: External Storage Setup — COMPLETE
- Formatted 4TB Samsung 990 PRO as APFS at `/Volumes/HestiaStorage` on Mac Mini
- Moved 138GB Ollama models to external via symlink (`~/.ollama/models → /Volumes/HestiaStorage/ollama-models/models`)
- Created `scripts/archive-logs.sh` (weekly log archival) + `scripts/backup-databases.sh` (nightly SQLite backup)
- Created `hestia/config/storage.yaml` — central config for all external paths
- Scheduled via crontab on Mac Mini: backup 3:30am daily, archive Sunday 2am
- Enabled SSH Full Disk Access + fixed GitHub SSH key on Mac Mini
- Commit: `c5d813a`

### Memory Graph Diversity — Code Complete
- Discovery: `docs/discoveries/memory-graph-diversity-2026-03-18.md`
- Second opinion: `docs/plans/memory-graph-diversity-second-opinion-2026-03-18.md` (Claude + Gemini approved)
- Plan: `docs/superpowers/plans/2026-03-18-memory-graph-diversity.md`
- 5 commits: `55cacc8` → `d3ecd80` → `a1e198f` → `8fbe0fa` → `beaec5b`
- 40 new tests (36 classification + 4 fact extraction), all passing
- LLM-backed classification with quality gates (promo email filter, Intelligence folder notes only)
- Retroactive reclassification script ready (`scripts/reclassify-conversations.py`)

### Inference Client Thinking Model Fix — FIXED
- **Root cause:** Qwen 3.5's thinking tokens consume `num_predict` budget, leaving `response` field empty
- Every `complete()` call returned empty strings on Mac Mini since Qwen 3.5 was installed
- **Fix:** Added `think` parameter to `_call_ollama` chain; tagger uses `think=False`
- This also explains why fact extraction has produced 0 facts since inception
- Commit: `8efe0c2` (push in progress with pre-push hook)

## In Progress

### Reclassification Deployment — Blocked on push completion
- Code is on Mac Mini but inference fix needs to land first
- After push: `git pull && python scripts/reclassify-conversations.py --limit 10` to verify
- Then `--apply` for full run (1,282 candidates after quality gate filtering)

### macOS Chat UX Issues — Researched, Not Started
Four issues identified from user screenshots, all code paths traced:

1. **Input field**: Dynamic height (36-200pt) exists in `CLITextView.swift` but user reports it doesn't resize. No formatting hotkeys (bold/italic). Check if `reportContentHeight()` is firing correctly.
   - Files: `HestiaApp/macOS/Views/Chat/CLITextView.swift`, `MacMessageInputBar.swift`

2. **Move Tia avatar to Command header**: Add avatar image left of greeting text in HeroSection. Remove large avatar from FloatingAvatarView (keep mode name + picker only).
   - Files: `HestiaApp/macOS/Views/Command/HeroSection.swift`, `HestiaApp/macOS/Views/Chat/FloatingAvatarView.swift`

3. **Thinking/loading state**: No visual between message send and first token. `isLoading` is set but no "thinking" bubble shown. Need to add a preparing/thinking indicator in `MacChatPanelView.swift` for the `isLoading && !isTyping` state.
   - Files: `HestiaApp/macOS/Views/Chat/MacChatPanelView.swift`

4. **Connection error**: "No connection available" — this was the inference client returning empty responses. Should be fixed by the thinking model fix above. Verify after deploy.

## Decisions Made
- LLM-first classification (not keyword heuristics) for Decision/Preference/Research types
- Confidence threshold 0.7 for chunk type promotion
- `think=False` for all structured inference calls (tagger, fact extraction) — thinking models waste tokens on reasoning for JSON output
- OBSERVATION chunks classified only from Intelligence folder (notes) and non-promo (mail)

## Test Status
- 40 new tests passing (classification + fact extraction)
- 2 pre-existing inference integration tests fail (same thinking model timeout — not affected by our fix since they don't pass `think=False`)
- 1 pre-existing error: `test_memory.py::TestMemorySource::test_query_filter_by_source`

## Uncommitted Changes
- `docs/discoveries/memory-graph-diversity-2026-03-18.md` (untracked — discovery report)
- `docs/plans/memory-graph-diversity-second-opinion-2026-03-18.md` (untracked — second opinion)
- `docs/superpowers/plans/2026-03-18-memory-graph-diversity.md` (untracked — plan)

## Known Issues / Landmines
- **Push may still be running** — pre-push hook runs full test suite + macOS build. Check `git log origin/main --oneline -1` to verify `8efe0c2` landed.
- **Mac Mini git state**: We did `git reset --hard origin/main` earlier to force-pull. Any local-only Mini changes are gone.
- **Fact extractor uses `client.generate()`** which doesn't exist on InferenceClient — it uses a separate import path. The fact extraction pipeline needs separate investigation to determine if it's using the Ollama Python library or a different client.
- **`_parse_tag_response` regex** (`r'\{[^{}]*\}'`) won't match nested JSON — if the LLM returns nested objects, parsing fails silently.

## Next Steps
1. **Verify push landed**: `git log origin/main --oneline -1` should show `8efe0c2`
2. **Pull on Mini + test inference**: `ssh andrewroman117@hestia-3.local 'cd ~/hestia && git pull && source .venv/bin/activate && python3 -c "import asyncio; from hestia.inference import get_inference_client; asyncio.run((lambda: get_inference_client().complete(\"Say hello\", think=False, validate=False))())"'`
3. **Run reclassification**: `python scripts/reclassify-conversations.py --limit 10` → verify counts → `--apply`
4. **macOS Chat UX** (4 items above — ~1.5h total Swift work)
5. **Commit untracked docs**: 3 plan/discovery files
