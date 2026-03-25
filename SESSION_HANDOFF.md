# Session Handoff — 2026-03-25 (iOS Fixes + Voice Conversation)

## Mission
Fix iOS TestFlight connection/crash issues (cert pinning, HealthKit) and implement bidirectional voice conversation mode (speak → Hestia responds with voice → auto-loop).

## Completed

### iOS Connection & Crash Fixes (v1.7.1–v1.7.4)
- **Cert pinning TOFU** (v1.7.1): Empty fingerprint in Keychain broke TLS on TestFlight. Added Trust-On-First-Use. (`CertificatePinning.swift`, `Configuration.swift`)
- **Stale fingerprint cleanup** (v1.7.2): Old empty `""` persisted across updates. Detect + delete invalid fingerprints on load. (`CertificatePinning.swift`)
- **HealthKit crash** (v1.7.4): `HKUnit(from: "mL/kg/min")` ObjC exception on iOS 26. Replaced with programmatic API. (`HealthKitService.swift`)

### Voice Conversation Mode (v1.8.0–v1.8.1, included in v1.9.0)
6 new files, 5 modified files, ~940 lines added:
- `TTSService.swift` — AVSpeechSynthesizer wrapper, sentence streaming, voice persistence
- `VoiceActivityDetector.swift` — RMS silence detection, 1.5s configurable threshold
- `VoiceConversationManager.swift` — State machine with dead-air "Hmm...", 60s watchdog, LLM task cancellation, audio interruption handling
- `VoiceConversationOverlay.swift` — Full-screen orb UI with state labels, transcript, response
- `VoiceSettingsView.swift` — Voice picker, VAD sensitivity, auto-continue toggle
- `ChatViewModel.sendAndStreamResponse()` — SSE tokens to TTS via callbacks (all 9 ChatStreamEvent cases)
- `SpeechService.onAudioLevel` — Callback for VAD
- `HestiaOrbState.speaking` — New enum case
- `ChatView.swift` — Conversation manager wired in

### Parallel Session Conflict (v1.8.1)
- `af90dc7` (cloud fix session) overwrote ChatView, stripped voice wiring. Restored in v1.8.1.
- v1.9.0 (Liquid Glass session) confirmed to include both design system AND voice conversation.

### Tailscale
- Confirmed authenticated on iPhone + MacBook Air. Mac Mini added during session.

## In Progress
- **Voice conversation device testing** — v1.9.0 on TestFlight, not yet verified working

## Decisions Made
- AVSpeechSynthesizer Phase 1, Kokoro CoreML Phase 2
- RMS-based VAD (not Silero) — sufficient for personal use
- `.voiceChat` audio session for hardware AEC
- Manager owns full loop — `processWithLLM()` internal, not view-triggered
- TOFU for self-signed cert pinning

## Test Status
- 3037 passing, 0 failing, 3 skipped
- pytest ChromaDB thread timeout (known, non-issue)

## Uncommitted Changes
- None (only `hestia/data/` untracked — runtime data)

## Known Issues / Landmines
- **16 orphaned agent worktrees** — clean up: `for wt in .claude/worktrees/agent-*/; do git worktree remove "$wt" 2>/dev/null; done`
- **ChatView is high-conflict** — parallel sessions overwrite each other. Check `git log -1 ChatView.swift` before editing.
- **AEC untested on hardware** — `.voiceChat` may not fully suppress echo on AirPods/Bluetooth. Validate.
- **VAD threshold 0.015** may be too aggressive in noisy environments — adjustable in Settings > Voice & Audio

## Process Learnings
- **7/9 tasks first-pass** (78%). Top blocker: parallel session overwriting ChatView (cost a full ship cycle).
- **Proposal 1 (HOOK)**: Pre-commit warning when staging a file modified by a different commit in the last hour.
- **Proposal 2 (CLAUDE.MD)**: Note ChatView as high-conflict file for parallel sessions.
- **Proposal 3 (SCRIPT)**: Auto-prune orphaned worktrees in /handoff.
- @hestia-critic + Gemini cross-validation caught real design issues (dead-air, control flow inversion, cancellation gap).

## Discovery & Plan Documents
- `docs/discoveries/voice-conversation-mode-2026-03-25.md` — SWOT, architecture research
- `docs/superpowers/plans/2026-03-25-voice-conversation-mode.md` — Implementation plan (11 tasks)
- `docs/plans/voice-conversation-mode-second-opinion-2026-03-25.md` — 3-model audit (APPROVE WITH CONDITIONS)

## Next Step
1. **Verify voice conversation on device** — TestFlight v1.9.0, voice mode (amber), tap mic, speak, confirm Hestia responds with voice and auto-loops
2. If crash: grab correct crash report (Settings > Privacy > Analytics > latest "HestiaApp" entry matching build 36+)
3. If works: Phase 1 complete. Phase 2 (Kokoro TTS) on roadmap.
4. **Clean up worktrees**: `for wt in .claude/worktrees/agent-*/; do git worktree remove "$wt" 2>/dev/null; done`
