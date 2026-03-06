# Session Handoff — 2026-03-05

## Mission
Fix CLI notes functionality (errors + timeouts), diagnose catastrophic model performance on MacBook Air M3, and design Apple metadata cache architecture for reliable tool calling with small local models.

## Completed
- **Notes CLI fix** (`4b986e7`): Two bugs — stale binary + iCloud account scoping. AppleScript now iterates `accounts -> folders` dynamically. Binary recompiled.
- **Hardware-adaptive model routing** (`1e742e4`): Speed-based detection after first inference. Auto-swaps qwen3.5:9b -> qwen2.5:7b if <8 tok/s. Auto-enables cloud smart mode. 10 new tests.
- **Apple metadata cache discovery** (`13fd101`): Full architecture designed in `docs/discoveries/apple-metadata-cache-smart-resolution-2026-03-05.md`. Option C: FTS5 cache + fuzzy resolver + smart tool resolution.
- **Documentation committed** (`13fd101`): CLAUDE.md updated (test count 1629, hw adaptation), SPRINT.md updated (Sprint 12A/12B scope), 8 discovery artifacts.

## In Progress
- Nothing — all work committed.

## Decisions Made
- **Speed-based hw detection over VRAM**: Apple Silicon reports 100% VRAM even under memory pressure. Tok/s is the reliable signal.
- **Option C: Apple metadata cache**: Daily sync of Apple data (Notes, Reminders, Calendar) into FTS5 SQLite + fuzzy resolver. Eliminates multi-step tool chains that 7B models can't handle. ADR pending during implementation.
- **rapidfuzz for fuzzy matching**: MIT license, C++ backend, best accuracy. New dependency.

## Test Status
- 1629 passing (1519 backend + 110 CLI), 0 failing, 3 skipped

## Uncommitted Changes
None — all committed.

## Known Issues / Landmines
- **qwen3.5:9b is unusable on MacBook Air M3** (4.5 tok/s). Hardware adaptation handles this automatically, but first request will be slow.
- **Council needs qwen2.5:0.5b on Mac Mini** — not yet pulled.
- **Notes CLI binary must be recompiled manually** after source changes: `cd hestia-cli-tools/hestia-notes-cli && swift build -c release && cp .build/release/hestia-notes-cli ~/.hestia/bin/`

## Next Step
Begin **Sprint 12: Apple Metadata Cache** implementation:
1. `pip install rapidfuzz` and add to requirements
2. Create `hestia/apple_cache/` module: `database.py` (FTS5 schema), `manager.py` (sync orchestration), `resolver.py` (fuzzy matching)
3. Start with Notes sync — reference `docs/discoveries/apple-metadata-cache-smart-resolution-2026-03-05.md`
4. Wire resolver into tool execution pipeline so models get pre-resolved entity IDs
