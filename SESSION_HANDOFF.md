# Session Handoff — 2026-03-17 (Session 5)

## Mission
Sprint 17: assign specialized open-source local models to each agent (Artemis/Apollo/Hestia) and add Claude Code-style reasoning streaming across all Hestia apps (CLI, iOS, macOS).

## Completed

### Feature A — Per-Agent Model Specialization
- **Artemis (Mira)** → `deepseek-r1:14b` (COMPLEX tier) — explicit chain-of-thought `<think>` blocks, 9GB VRAM, fits M1 16GB
- **Apollo (Olly)** → `qwen3:8b` (CODING tier) — native Ollama tool calling + strong coding, replaces `qwen2.5-coder:7b`
- **Hestia (Tia)** → `qwen3.5:9b` (PRIMARY) — unchanged, best sub-10B general model
- Config: `config/orchestration.yaml` — new `agent_model_preferences` section
- Config: `hestia/config/inference.yaml` — coding_model→qwen3:8b, complex_model→deepseek-r1:14b (enabled: true)
- Code: `hestia/orchestration/agent_models.py` — `AgentModelPreference` dataclass + `OrchestratorConfig` update
- Code: `hestia/inference/router.py` — `route_for_agent()`, `set_agent_model_preferences()`
- Code: `hestia/orchestration/executor.py` — `force_tier` per agent in `_execute_task()`
- Code: `hestia/orchestration/handler.py` — agent prefs wired via `_get_orchestrator_config()`
- Models pulled locally: `deepseek-r1:14b` (9.0GB), `qwen3:8b` (5.2GB)

### Feature B — Reasoning Streaming (Claude Code-style)
- **Backend**: 5 new `reasoning` yield points in `handle_streaming()` — intent classification, agent routing, memory retrieval, model selection, `<think>` blocks
- **`<think>` parser**: intercepts DeepSeek R1 thinking tokens mid-stream, routes as `reasoning` events, strips from stored content
- **CLI**: `REASONING` enum in `models.py`, `_render_reasoning()` in `renderer.py` — transient `⟳`/`💭` status lines that clear on first response token
- **Swift**: `.reasoning(aspect:summary:content?)` case in `ChatStreamEvent` + parser in `Response.swift`
- **Models**: `ReasoningStep` struct + `reasoningSteps: [ReasoningStep]?` on `ConversationMessage` in `Message.swift`
- **iOS/macOS ViewModels**: `.reasoning` handler appends steps to message during stream
- **iOS/macOS Views**: `ReasoningStepsSection` collapsible component above AI message content
- **Shared**: `HestiaShared/Sources/HestiaShared/Views/ReasoningStepsSection.swift` (new file)

### Commits on main
- `220e709` feat: Sprint 17 — per-agent model specialization + reasoning streaming (13 files, +351/-16)
- `6bb97fb` fix: update test assertions for Sprint 17 model changes
- Other commits (`b575296`, `c12c674`, `9c39967`, `7be950f`, `ff082a9`) from parallel session — CI/CD fixes + Sprint 17 learning closure (CorrectionClassifier, OutcomeDistiller)

## In Progress

**Parallel worktree session (`awesome-nash`) left uncommitted changes on main working tree:**
These are NOT from this session — they appear to be a macOS Memory Browser + Learning Metrics UI sprint:

Modified (tracked):
- `hestia/api/routes/memory.py` — new memory browser endpoints
- `hestia/api/routes/research.py` — research graph changes
- `hestia/memory/database.py` — new queries
- `hestia/research/database.py` + `graph_builder.py` — graph changes
- Multiple macOS view/viewmodel files (AppDelegate, IconSidebar, ResearchView, etc.)

Untracked (new files):
- `HestiaApp/macOS/Views/Memory/` — Memory Browser views
- `HestiaApp/macOS/Models/MemoryBrowserModels.swift`
- `HestiaApp/macOS/Services/APIClient+Memory.swift` + `APIClient+Learning.swift`
- `HestiaApp/macOS/ViewModels/MacMemoryBrowserViewModel.swift`
- `HestiaApp/macOS/Views/Command/LearningMetricsPanel.swift`
- `HestiaApp/macOS/Models/LearningModels.swift`
- `tests/test_memory_browser.py` + `tests/test_research_graph.py`

## Decisions Made
- **Artemis model**: DeepSeek-R1-14B chosen over Phi-4-reasoning (32K context too small) and QwQ-32B (doesn't fit M1)
- **Apollo model**: Qwen 3 8B chosen over Hermes 3 (weaker coding) and NexusRaven (13B overhead)
- **M5 Ultra upgrade path**: Hestia→qwen3.5:27b, Artemis→QwQ-32B, Apollo→qwen2.5-coder:32b — all ~57GB, simultaneous load
- **Reasoning verbosity**: Medium (intent+agent+memory+model+thinking), always on, all apps, show summaries
- **`<think>` handling**: stream lines as `reasoning` events in real-time, strip tags from stored response

## Test Status
- **Backend**: 2132 tests collected, all passing
- **CLI**: 135 passing
- **Pre-push gate**: passed (tests + macOS xcodebuild on main branch)
- **iOS build**: clean
- **macOS build**: clean (required `xcodegen generate` after new SPM `Views/` directory)

## Uncommitted Changes
16 files modified/untracked from parallel session (Memory Browser + Learning Metrics UI). **Do not commit blindly** — review first.

## Known Issues / Landmines
- **`test_simple_completion` (integration test)**: `@pytest.mark.integration`, requires live Ollama. Flaky in mock env — pre-existing, not Sprint 17. Pre-push hook handles it gracefully.
- **`_get_orchestrator_config()` called twice in streaming path**: once to wire agent prefs into router, once for routing decision display. YAML parse is fast (~1ms) but worth caching eventually.
- **xcodegen required after new SPM directories**: Adding `HestiaShared/Sources/HestiaShared/Views/` required `xcodegen generate` before macOS build. Not obvious — add to Swift change workflow.
- **Models only pulled on dev Mac**: `deepseek-r1:14b` and `qwen3:8b` need to be pulled on Mac Mini after deploy. CI/CD won't auto-pull them. Run manually: `ollama pull deepseek-r1:14b && ollama pull qwen3:8b`
- **Reasoning events in non-streaming path (`handle()`)**: only `handle_streaming()` emits reasoning events. The REST endpoint still uses the non-streaming handler — reasoning won't show for non-streaming iOS clients that fall back to REST. Low priority since streaming is the default.

## Process Learnings

### Config Gaps
- **Model name assertions in tests**: 3 tests hardcoded `qwen2.5-coder:7b` — broke when config changed. Tests should reference `router.coding_model.name` dynamically. Add to lessons.md.
- **xcodegen after SPM directory creation**: Should be documented in CLAUDE.md under iOS Specifics as a required step after adding new `HestiaShared/Sources/` subdirectories.

### First-Pass Success Rate: ~90%
- Backend logic: first-pass correct
- One fix: `intent.primary_intent` vs `intent` passed to `AgentRouter.resolve()`  — caught immediately
- One env issue: xcodegen stale cache — 30s fix
- Test fixture update: expected model name change — 3 lines

### Agent Orchestration
- Parallel @hestia-explorer agents (2 simultaneously) worked well for Phase 1 research
- @hestia-build-validator caught macOS failure before push — high ROI
- @hestia-tester ran targeted tests efficiently — avoided full suite overhead mid-sprint
- Missed: `xcodegen generate` should be part of the standard post-Swift-change checklist

## Next Step

**Immediate: clean up working tree first.**

1. Review uncommitted parallel session work:
   ```bash
   git diff hestia/api/routes/memory.py hestia/api/routes/research.py | head -50
   cat tests/test_memory_browser.py
   ```
2. Run new tests: `python -m pytest tests/test_memory_browser.py tests/test_research_graph.py -v`
3. Run `xcodegen generate` in `HestiaApp/` and verify macOS build compiles
4. Commit the parallel session's work with a meaningful message
5. Then check `SPRINT.md` to identify what Sprint 18 looks like — the parallel session's Memory Browser work may already be it

**Also needed on Mac Mini:**
```bash
ollama pull deepseek-r1:14b
ollama pull qwen3:8b
```
(models are on dev Mac, not yet on the deployment target)
