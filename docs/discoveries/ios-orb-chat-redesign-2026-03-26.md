# Discovery Report: iOS Chat View Redesign — "Orb UI"
**Date:** 2026-03-26
**Confidence:** High
**Decision:** Redesign ChatView to an orb-centered layout with scrollable message history below the orb, keeping the TabBar visible but minimal. Fix conversation mode crash via audio session lifecycle hardening.

## Hypothesis
Replace the current message-bubble chat interface with a minimal, orb-first experience where the HestiaOrbView is the visual center, greeting text appears above, and a single input bar sits at the bottom. The standard TabBar would be hidden by default and revealed via swipe-up gesture. Audio icon interaction: single tap = transcription mode, long press (3s) = conversation mode.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** HestiaOrbView already exists and is production-quality (Canvas + TimelineView, 4 states, audio-level reactivity, Fresnel rim, 8 fluid layers). Design system colors (#FF9F0A amber palette) are consistent. VoiceConversationOverlay already uses the orb successfully. ChatViewModel/SpeechService/TTSService are well-architected with clean separation. iOS 26.0+ target means latest APIs available. | **Weaknesses:** Current orb uses Canvas drawing (CPU-intensive on older devices at 30fps with 8 gradient layers). Conversation mode crash is undiagnosed — likely audio session conflict between AVAudioEngine and AVSpeechSynthesizer. No existing gesture infrastructure for hidden tab bar. Message history is core to the chat experience — removing it entirely is risky. |
| **External** | **Opportunities:** ChatGPT voice mode and Google Gemini both use orb-centered UIs in production — validates the pattern. Siri iOS 18+ moved away from classic orb to border glow, leaving design space. metasidd/Orb open-source SwiftUI package demonstrates the pattern is achievable. Users increasingly expect ambient, personality-driven AI interfaces. | **Threats:** Apple HIG explicitly states tab bars should remain visible — hiding it violates platform conventions and hurts discoverability. Users who rely on message history (most chat users) will be frustrated if it's removed. Performance risk on iPhone 12/13 class devices with complex Canvas animations. Audio session conflicts are a known iOS pain point with no clean universal fix. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Orb-centered layout with greeting + input bar (core redesign). Fix conversation mode crash (audio session). Keep message history accessible (scroll up from orb). | Audio icon tap/long-press gesture mapping (nice UX polish). |
| **Low Priority** | Particle wave variant (HTML mockup style — significant effort, SwiftUI Canvas may struggle). | Hidden tab bar via swipe-up (HIG violation, discoverability risk). |

## Argue (Best Case)

**The orb-first UI is the right direction, with evidence:**

1. **ChatGPT and Gemini validate the pattern.** Both use animated visual elements (orb/waves) as the primary interface for voice interactions. ChatGPT hides its tab bar during voice chat, creating an immersive experience. This is becoming the expected AI assistant aesthetic.

2. **The existing HestiaOrbView is excellent.** 446 lines of production-quality Canvas rendering with 4 states, warped circle paths, Fresnel rim lighting, atmospheric glow, and audio-level reactivity. It already works in VoiceConversationOverlay. Promoting it to the main chat view is a natural evolution.

3. **Minimal UI increases perceived intelligence.** When the interface is just an orb + greeting + input, the assistant feels more like a presence than a tool. This aligns with Hestia's Jarvis-like identity. The greeting text ("Morning, Boss.") already exists in ChatView.

4. **Technical feasibility is high.** The orb exists. The input bar exists. The greeting logic exists. The redesign is primarily layout restructuring, not new component creation. Estimated effort: 12-18 hours.

5. **Voice interaction improvements.** Single-tap for transcription and long-press for conversation mode is more intuitive than the current 3-mode cycle button. It simplifies the mental model.

## Refute (Devil's Advocate)

**Critical risks that could sink this redesign:**

1. **Message history is non-negotiable.** Every production AI assistant that uses an orb UI still provides scrollable message history. Gemini shows it above the orb. ChatGPT shows it in a sidebar. Removing chat bubbles entirely would frustrate users who want to reference previous responses, copy text, or review context.

2. **Hidden tab bar is a UX anti-pattern on iOS.** Apple's HIG explicitly states: "A tab bar should remain visible." No major production iOS app hides the tab bar with a swipe gesture. Discoverability is the killer — users won't know Command and Settings exist. This is the single highest-risk element of the proposal.

3. **Performance concerns are real.** The current HestiaOrbView runs at 30fps with 8 gradient fluid layers, specular highlights, and Fresnel rim on Canvas. On iPhone 12 (A14), this draws ~1,920 gradient fills per second. Adding this to the main chat view (always visible, not just during voice conversation) means constant GPU/CPU load. Battery drain will be noticeable.

4. **Conversation mode crash needs diagnosis, not UI changes.** The crash is almost certainly an audio session conflict — AVAudioEngine (speech recognition) and AVSpeechSynthesizer (TTS) fighting over the .playAndRecord session. The current code configures the session once in `configureAudioSession()` but doesn't deactivate/reactivate between listen and speak transitions. This is a services-layer bug, not a UI bug.

5. **Scope creep risk.** The Figma prompt describes a "particle wave field with 2000-5000 particles" — that's a WebGL-class animation, not achievable in SwiftUI Canvas at acceptable frame rates. The existing orb (fluid sphere) is the right visual, not the particle wave.

## Third-Party Evidence

### Production Precedents
- **ChatGPT iOS voice mode:** Uses an animated orb/sphere, hides chrome during voice conversation, shows message bubbles in text mode. Dual-mode approach — orb for voice, bubbles for text.
- **Google Gemini:** Animated waves (not orb), history displayed above in scrollable view. Tab bar remains visible as part of Google app.
- **Siri (iOS 18+):** Moved AWAY from orb to edge-glow pattern. No message history. System-level overlay, not an app.
- **metasidd/Orb (open source):** MIT-licensed SwiftUI orb with configurable colors, particles, glow. Validates that high-quality orb animation is achievable in pure SwiftUI. Uses MeshGradient (iOS 18+) which is more GPU-efficient than Canvas path drawing.

### Audio Session Crash Research
The `.playAndRecord` + `.voiceChat` combination is the correct configuration for simultaneous recognition + TTS. Known crash patterns:
- Not handling `interruptionNotification` (Hestia does handle this — good)
- Not deactivating session before reconfiguring (Hestia deactivates in `stop()` but not between listen/speak transitions)
- AVSpeechSynthesizer internal conflicts with active AVAudioEngine input taps
- **Most likely root cause:** The `transitionToProcessing` method calls `ttsService.speak("Hmm...")` while the AVAudioEngine input tap may still be active. The speech recognition `stopTranscription()` is async, so there's a race condition.

## Gemini Web-Grounded Validation
**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- Apple HIG explicitly states tab bars should remain visible — hiding is discouraged
- ChatGPT uses orb for voice mode, confirming the pattern is production-viable
- Google Gemini uses animated visual element with scrollable history above it
- AVAudioSession .playAndRecord with .voiceChat is the correct category for this use case
- No major iOS app hides the tab bar and reveals it with a gesture

### Contradicted Findings
- Initial assumption that hiding the tab bar is a viable pattern — Gemini confirms it's not recommended and no production apps do it
- Assumption that users are fine without message history — all production orb UIs still provide history access

### New Evidence
- Siri moved AWAY from orb to edge-glow in iOS 18, suggesting the orb pattern is not universally superior
- The "separate history view" approach (sidebar in ChatGPT) is a viable alternative to inline scrolling
- Audio session deactivation/reactivation between transitions is a recommended workaround for conflicts

### Sources
- [Apple HIG: Tab Bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)
- [metasidd/Orb GitHub](https://github.com/metasidd/Orb)
- [Apple: Handling Swipe Gestures](https://developer.apple.com/documentation/uikit/handling-swipe-gestures)
- [SwiftUI Canvas + TimelineView](https://www.hackingwithswift.com/quick-start/swiftui/how-to-create-custom-animated-drawings-with-timelineview-and-canvas)

## Philosophical Layer
- **Ethical check:** No concerns. This is a personal UI improvement for a private assistant.
- **First principles:** The orb works because it gives the AI a "presence" — it's not just a text box, it's an entity. This is philosophically aligned with Hestia's identity as Jarvis-like. But the presence should enhance the utility, not replace it. Message history IS utility.
- **Moonshot:**

### Moonshot: Contextual Morph UI
Instead of choosing between orb and chat bubbles, the view morphs based on interaction mode:
- **Idle state:** Orb centered, greeting text, input bar. Clean, ambient, Jarvis-in-standby.
- **Text conversation:** User sends a message, orb smoothly scales down and moves to the top/header position (like the current avatar), message bubbles appear below. Standard chat UX.
- **Voice conversation:** Orb expands to center stage, message bubbles fade, transcript appears ephemerally below orb (current VoiceConversationOverlay behavior, but inline).
- **Returning to idle:** After inactivity (30s?), messages scroll away, orb returns to center.

**Technical viability:** High — it's animation transitions between existing layouts, not new rendering.
**Effort estimate:** 20-25 hours (vs. 12-18 for simple orb layout).
**Risk:** Animation complexity, edge cases during transitions.
**MVP scope:** Just the idle-state orb view + transition to chat bubbles on first message.
**Verdict:** PURSUE — This is the elegant solution. It gives Andrew the orb-first aesthetic without sacrificing chat utility.

## Key Principles Score
| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No security surface changes |
| Empathy | 4 | Orb-first is more engaging; must preserve message history access |
| Simplicity | 3 | Morphing UI adds complexity but eliminates the forced choice between orb and chat |
| Joy | 5 | The orb is genuinely beautiful and brings personality to the assistant |

## Recommendation

**Implement the Contextual Morph UI (moonshot) as a phased approach:**

### Phase 1: Orb Idle State (8-10h)
- Restructure `ChatView` so that when `messages` is empty, the view shows: orb centered + greeting text + input bar (no header, no message list)
- Keep existing `MainTabView` with visible TabBar (do NOT hide it)
- Add `.speaking` state to `HestiaOrbState` (currently maps to `.success` which is confusing)
- Optimize orb for always-visible use: reduce to 20fps when idle, 30fps when active

### Phase 2: Morph Transition (6-8h)
- When user sends first message, orb animates: scale down + move to header position
- Message bubbles appear with staggered opacity transition
- Orb in header position replaces current avatar, pulses during loading/thinking
- Tapping header orb returns to orb-centered view (clears messages or scrolls to top)

### Phase 3: Voice Interaction Redesign (4-6h)
- Replace 3-mode cycle button with: tap mic = transcription, long-press mic (haptic at 1s) = conversation mode
- Remove separate `VoiceConversationOverlay` — conversation mode happens inline with orb expanded
- Keep journal mode accessible via context menu on mic button

### Phase 4: Fix Conversation Mode Crash (3-4h)
- Root cause: race condition in `VoiceConversationManager.transitionToProcessing()` — calls `ttsService.speak()` before `speechService.stopTranscription()` completes
- Fix: await `stopTranscription()` before any TTS, deactivate/reactivate audio session between transitions
- Add `do/catch` around `configureAudioSession()` with graceful fallback

**Total estimate: 21-28 hours across 4 phases.**

### What NOT to do:
1. Do NOT hide the TabBar — it violates HIG, has zero production precedent, and hurts discoverability
2. Do NOT implement the particle wave from the Figma prompt — it requires 2000-5000 particles, which is WebGL territory, not SwiftUI Canvas
3. Do NOT remove message history — every production AI assistant preserves it
4. Do NOT use the HTML mockup orb variant — the existing SwiftUI HestiaOrbView is superior for native performance

**Confidence: High.** The orb-first aesthetic is validated by ChatGPT and Gemini. The morphing approach preserves chat utility. The conversation crash has a clear probable root cause. The tab bar must stay visible per HIG.

### What would change this recommendation:
- If Apple introduces a new "immersive mode" API in iOS 27 that officially supports hidden tab bars
- If testing reveals the orb at 20fps idle still causes unacceptable battery drain (would need to add a "sleep" mode)
- If the morphing transition proves too janky in practice (fallback: simple toggle between orb view and chat view, no animation)

## Final Critiques

- **Skeptic:** "The morphing UI sounds cool but won't the transitions be janky?" Response: The transitions are standard SwiftUI `.matchedGeometryEffect` and `.animation()` — not custom Canvas work. SwiftUI excels at layout animations. The orb itself doesn't need to re-render during the transition, just its frame. If it proves janky, the fallback is a simple crossfade between two layouts.

- **Pragmatist:** "Is 21-28 hours worth it for a chat view redesign?" Response: The chat view is the primary interface for the iOS app — it's what Andrew sees every time he opens Hestia. The current view is functional but generic (looks like any chat app). The orb gives Hestia visual identity and personality. Plus, Phase 4 (conversation crash fix) is a standalone bug fix worth doing regardless.

- **Long-Term Thinker:** "What happens when you add more features to the chat view?" Response: The morphing pattern actually helps here. New features (tool results, inline cards, etc.) go in the chat-bubble state, which has the full message list infrastructure. The orb idle state stays clean and minimal. It's a better separation of concerns than the current monolithic ChatView.

## Open Questions
1. Should the orb have a "sleep" mode (static image) after 60s of inactivity to save battery?
2. Should the morph transition be `.matchedGeometryEffect` (smooth geometry animation) or a simpler crossfade?
3. What's the exact long-press duration for conversation mode — 1s (standard iOS) or 3s (as specified)?
4. Should the journal mode move to a separate entry point (e.g., Command tab) or stay as a context menu option on the mic?
5. Does Andrew want the particle wave aesthetic (from the Figma prompt) as a future exploration, or is the current sphere orb the final visual direction?
