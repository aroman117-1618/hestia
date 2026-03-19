# Discovery Report: Graph View Refinement + Explore Navigation + Command Tab Modernization
**Date:** 2026-03-19
**Confidence:** High
**Decision:** Three-part UI overhaul: (1) Restructure Graph View into Principle-centric knowledge display with conversational node feedback, (2) Simplify Explore nav from 3 tabs to 2, (3) Modernize Command tab — strip chat chrome, redesign Orders as a wizard under System.

## Hypothesis

**RQ1 — Graph View:** The current graph visualizes all 7 node types equally, including low-value CONVERSATION chunks that dominate the view. Restructuring to show Preference/Fact/Decision as primary nodes — with Insights, Observations, and Research as sidebar context — plus adding a conversational feedback mechanism that feeds into nightly Principle distillation, would make the graph actionable rather than decorative.

**RQ2 — Explore Nav:** The Resources tab overlaps with Files and Inbox content. Collapsing it under Files as a sub-tab simplifies the mental model from 3 top-level concepts to 2.

**RQ3 — Command Tab:** The chat window's avatar header and greeting text consume vertical space that should belong to messages. Modern AI code editors (Cursor, VS Code Copilot) have converged on content-first layouts where the input box is the hero element. Orders (scheduled prompts) should live under System as a wizard-based flow rather than an inline form.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** PrincipleStore + OutcomeDistiller already exist. `/v1/research/graph` accepts `node_types` filter param. Approve/Reject UI for principles already built. APScheduler nightly loop infrastructure in place. `FloatingAvatarView` is a self-contained 214-line file — clean removal. macOS `SystemActivityView` already shows orders as "Active Workflows" — the navigation move is half-done. | **Weaknesses:** "Investigate in Explorer" button is stubbed. No feedback model or API endpoint for non-principle nodes. OutcomeDistiller runs weekly (not nightly). Conversational feedback needs a mini-chat UI inside NodeDetailPopover — non-trivial SwiftUI work. iOS `ChatView.header` is tightly coupled to `avatarPosition` (used for ripple effect on mode switch). Orders wizard (3-step) is 8h of new SwiftUI — largest single item. |
| **External** | **Opportunities:** ChatGPT Pulse validates the nightly-review-morning-briefing pattern at scale (Pro users, shipped 2025). InfraNodus shows AI-enhanced graph views are the growth direction for PKM. Semantic zoom research provides a proven UX pattern for primary vs. structural nodes. Multi-step forms show 86% higher conversion rates than single-step for complex input (UX research). | **Threats:** Conversational feedback parsing is fragile — LLM must reliably extract intent from freeform node annotations. Risk of "principle sprawl" if distillation isn't selective enough. Cursor forum users pushed back on frequent layout changes — removing a familiar header could feel disorienting if not replaced with clear affordances. Limitless/Rewind shutdown (Dec 2025) shows personal knowledge tools face retention risk if the curation UX becomes a chore. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Graph default filter to P/F/D primary + structural connector nodes; Remove Tia header (iOS + macOS) — immediate content-first gain; Conversational feedback endpoint + nightly processing; Resources sub-tab under Files | Semantic zoom (show more node types on zoom-in); Session management relocation |
| **Low Priority** | Principle proposal reasoning display (show *why* Hestia linked memories); Orders Past/Upcoming temporal split | Graph animation polish; Resources search within sub-tab; Orders wizard template suggestions |

## Argue (Best Case)

**Graph View refinement:**
- The existing `node_types` filter on `/v1/research/graph` means the API change is zero-effort — it's a UI default change in `MacNeuralNetViewModel.GraphMode.defaultNodeTypes`.
- PrincipleStore already handles PENDING -> APPROVED -> REJECTED lifecycle. Extending it to handle feedback-driven proposals is additive, not a rewrite.
- Conversational feedback aligns with how Andrew naturally interacts — low-friction, natural language, same pattern as chat.
- Nightly processing via the existing LearningScheduler is a 1-2 hour addition to wire a new monitor.
- ChatGPT Pulse proves the "overnight curation -> morning review" UX works at consumer scale — their implementation does exactly this with chat history and memories.

**Explore cleanup:**
- iOS already uses a unified view with filter chips — this aligns macOS closer to iOS UX patterns.
- Resources content (drafts, notes, tasks) is conceptually "files" — the mental model is cleaner.
- Reduces cognitive load: 2 tabs instead of 3, each with a clear domain (Files = stuff, Inbox = incoming).

**Command Tab modernization:**
- `FloatingAvatarView` takes 70px of vertical space (line 88: `.frame(height: 70)`). That's 8-10% of a typical MacBook display for a greeting and avatar that provides no actionable information.
- Cursor's UI evolution confirms the trend: they removed their agents/editor toggle from the top nav in favor of compact inline controls. Users requested less chrome, more content.
- The mode picker already exists as a popover in `FloatingAvatarView` — moving it to a pill in the input bar is a relocation, not a redesign.
- Multi-step wizard UX research shows 86% higher completion rates than single-step forms for complex input with 5+ fields. Orders have 6 fields across 3 distinct mental models (prompt, resources, schedule) — a perfect wizard candidate.
- `SystemActivityView` already renders orders under "Active Workflows" — the iOS `OrdersWidget` just needs its standalone placement removed.

## Refute (Devil's Advocate)

**Graph View:**
- Conversational feedback is the hardest piece. Unlike thumbs up/down, parsing "this is outdated, merge with the preference about morning routines" requires reliable intent extraction. Edge cases: vague feedback, contradictory feedback across sessions, feedback about nodes that reference other nodes.
- Principle sprawl risk: if the nightly loop proposes too many Principles, the review UX becomes a chore rather than a curated insight. Need strong dedup (already have 0.85 cosine threshold) plus a confidence gate. Limitless/Rewind's cautionary tale: they captured everything and users drowned in data — curation selectivity is existential.
- The 3D SceneKit graph is already complex code. Changing the default filter and adding a mini-chat to NodeDetailPopover touches two high-complexity files simultaneously.

**Explore cleanup:**
- Resources currently surfaces drafts, mail, tasks, notes, AND files in one list. Moving it under Files creates a sub-tab that's almost as broad as the original tab — are we just moving the problem one level deeper?
- Users who primarily use Resources for drafts may find the extra click (Files -> Resources sub-tab) annoying.

**Command Tab:**
- The greeting ("Morning, Boss.") is a personality touch that makes Hestia feel alive. Removing it makes the UI more sterile — Hestia becomes "just another tool" rather than an assistant with character. Counter: personality can live in message content and response tone, not in static header text.
- iOS header removal requires handling the `avatarPosition` state used for the mode-switch ripple effect. The ripple either needs a new anchor point or removal. Not hard, but it's a coupled change.
- The Orders wizard (8h) is the largest single item and the least essential. Current inline form works — it's just not optimal. Could defer to later sprint without blocking other value.
- Cursor forum megathread shows user frustration with layout changes that happen without consent. Lesson: if removing the header, ensure the replacement affordances (mode pill, session button) are immediately discoverable.

## Third-Party Evidence

**Knowledge graph UX:** InfraNodus (Obsidian plugin) addresses the core problem — default graph views in PKM tools are "unusable for day-to-day work and ideation." Their solution: AI-generated research questions that bridge structural gaps, plus topic-level filtering. This validates the need for filtering and AI-enhanced curation.

**Knowledge graph feedback (2025-2026):** Industry best practice has evolved to multi-dimensional, human-in-the-loop refinement. KONDA (SCI-K 2025) demonstrates a tool maintaining human-in-the-loop validation where each extraction can be reviewed, edited, or extended, with inputs in natural language. The pattern: granular flagging (Factually Incorrect, Outdated, Redundant, Schema Mismatch), confidence calibration (display + allow dispute), attribute-level feedback. Hestia's approach aligns — the narrow intent taxonomy (merge, outdated, correct, relate, delete) matches the "granular flagging" pattern.

**Principle distillation:** Mem0's knowledge graph MCP integration demonstrates that the industry is moving from vector-only storage to explicit entity-relationship graphs for cross-conversation understanding. The pattern of "auto-extract -> human review -> approved knowledge" is becoming standard.

**Semantic zoom:** ACM research on ontology graph visualization describes a 3-layer approach: abstract overview -> intermediate detail -> full detail, with discrete levels that show more information as users zoom in. This maps directly to the P/F/D primary + structural connector approach.

**Nightly curation:** ChatGPT Pulse performs nightly asynchronous research across chat history and memories, generates morning briefing cards with thumbs up/down and "curate" controls. Each night, it synthesizes information from memory, chat history, and direct feedback to learn what's most relevant, then delivers personalized updates the next day. Key UX pattern: visual cards with expand/dismiss, teaching preferences through interaction. Hestia's approach is more sophisticated (conversational feedback vs. thumbs) but the core loop is validated.

**Personal knowledge retention risk:** Limitless (formerly Rewind AI) was acquired by Meta in December 2025 and discontinued its hardware. Their core challenge was the same one Hestia faces: capturing everything is easy; curating what matters is hard. Their "searchable, encrypted database of your entire existence" proved that without strong curation, users drown. Hestia's principle distillation with human approval is the right counter — but the feedback processor must be aggressive about filtering (max 3-5 proposals per nightly run).

**Chat UI trends:** Cursor's layout megathread reveals user tension — developers want minimal chrome but also want discoverable controls. The team responded by making layouts customizable and removing forced changes. VS Code Copilot introduced a redesigned model picker (March 2026) focused on search, sections, and rich hover details — compact inline controls, not header-level UI. Pattern confirmed: input box as hero, mode/model selection as compact inline control.

**Multi-step form research:** Multi-step forms demonstrate 86% higher conversion rates than single-step forms (WebStacks 2025). Inline validation reduces errors by 22% and completion time by 42%. Key finding: sequential logic and conditional disclosure work best when steps involve distinct mental models. Orders have 3 distinct mental models (what, where, when) — making the wizard the right pattern. However, for simple 5-field forms, single-page can outperform wizards. The recommendation: wizard for creation, inline for quick edits.

## Gemini Web-Grounded Validation
**Model:** Gemini 2.5 Pro (thinking + codebase analysis)

### Confirmed Findings
- Hestia's bi-temporal tracking, source provenance, and principle distillation (requiring approval) align with 2025 best practices for knowledge graph quality control.
- The narrow intent taxonomy (merge, outdated, correct, relate, delete) matches the industry-standard "granular flagging" pattern for node feedback.
- Multi-dimensional feedback (not just thumbs up/down) is the current best practice — Hestia's conversational approach is ahead of the curve.

### Contradicted Findings
- None materially contradicted. Gemini's analysis confirmed the SWOT assessment without surfacing blocking issues.

### New Evidence
- **FactStatus extension recommendation:** Gemini suggested extending `FactStatus` enum to include `FLAGGED` and `UNDER_REVIEW` states, which would provide a natural status for nodes receiving negative feedback before the nightly processor runs. This is a low-cost improvement worth adding.
- **Retrieval utility feedback:** If a retrieved node leads to a hallucination in chat, the feedback loop should trace back and flag that specific node as "Low Utility." This connects the graph feedback system to the existing OutcomeTracker — outcomes with negative feedback could auto-flag the memory chunks that were retrieved.
- **Community summarization feedback propagation:** Feedback on community-level summaries should propagate down to individual contributing nodes. This matters for the graph's community clustering feature.

### Sources
- [KONDA: Semantic Annotation with Human-in-the-Loop (SCI-K 2025)](https://sci-k.github.io/2025/papers/paper14.pdf)
- [Knowledge Graph Construction with LLMs (Nature Scientific Reports 2026)](https://www.nature.com/articles/s41598-026-38066-w)
- [From LLMs to Knowledge Graphs: Production-Ready Systems 2025](https://medium.com/@claudiubranzan/from-llms-to-knowledge-graphs-building-production-ready-graph-systems-in-2025-2b4aff1ec99a)

## Philosophical Layer

### Ethical Check
All three features serve genuine user needs: reducing information overload (graph filtering), simplifying navigation (explore cleanup), and removing friction from the primary interaction surface (chat chrome removal). No ethical concerns. The conversational feedback system stores user annotations locally — no external data sharing. The nightly processing happens on local hardware. Privacy posture is maintained.

### First Principles Challenge
**Why this approach?** Strip away assumptions:
- The graph exists to help Andrew understand what Hestia knows. Currently it shows everything equally, which means it shows nothing effectively. Filtering is the minimum viable improvement. Feedback makes it bidirectional.
- The Explore tabs exist because three data domains were built at different times (Files Sprint 9A, Inbox Sprint 9B, Resources Sprint 8). The 3-tab structure reflects build order, not user mental model. Merging reflects actual usage.
- The chat header exists because early Hestia UX was inspired by consumer chat apps (iMessage, WhatsApp). But Hestia is a power tool, not a social app. Power tools prioritize content density over branding.
- **10x better:** The moonshot version is a unified canvas where graph, chat, and file explorer are spatially arranged panels that the user can drag-resize, with graph nodes directly droppable into chat as context. Think Figma's spatial canvas but for knowledge + conversation. This is Sprint 35+ territory.

### Moonshot: Spatial Knowledge Canvas
**What's the moonshot version?** A unified canvas where the knowledge graph, chat, file browser, and orders are not separate tabs but spatially arranged panels on an infinite canvas. Click a graph node -> it opens a detail card in-place. Drag a node into the chat area -> it becomes context for the next message. Draw a line between two nodes -> Hestia explains the relationship.

**Technical viability:** SwiftUI 6.0 (WWDC 2026) is rumored to improve ScrollView and canvas APIs. SceneKit could be replaced with RealityKit or Metal for better 2D/3D hybrid rendering. The core data layer (graph API, chat API, file API) already exists — it's a UI unification problem, not a data problem.

**Effort estimate:** 80-120 hours across 4-6 sprints. Requires deep SceneKit/Metal knowledge and a new layout engine.

**Risk assessment:** High. Spatial UIs look great in demos but often fail in practice because users fall back to familiar tab-based navigation. Figma succeeded because the canvas IS the work product. For Hestia, the canvas would be a meta-layer over the work product.

**MVP scope:** A single "Focus Mode" where clicking a graph node opens a side panel with chat pre-populated with that node as context. 10h to build.

**Verdict:** SHELVE. The Focus Mode MVP (10h) is worth doing in Sprint C as a stretch goal. The full spatial canvas requires WWDC 2026 SwiftUI improvements and the M5 Ultra hardware upgrade. Revisit Q3 2026.

### Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | All feedback stored locally. No new external communication. Nightly processing uses local LLM or existing cloud pipeline with PII safety. |
| Empathy | 5 | Every change reduces friction: less visual noise (graph filter), fewer tabs (explore), less wasted space (header removal), clearer wizard (orders). |
| Simplicity | 4 | Graph filter + explore cleanup are pure simplification. Chat header removal is clean. Orders wizard adds complexity but replaces a worse form. Deducted 1 point for the feedback processor's inherent complexity. |
| Joy | 4 | The graph becoming actionable rather than decorative is deeply satisfying. Chat content-first layout feels modern. Orders wizard is well-structured. Deducted 1 point because removing the "Morning, Boss." greeting loses a personality touch. |

## Recommendation

### Feature 1: Graph View Refinement

**Architecture:**

1. **Default filter change** (trivial): Update `GraphMode.defaultNodeTypes` in `MacNeuralNetViewModel.swift`. Legacy mode: `["topic", "entity", "principle"]` (drop `memory` from default). Facts mode: `["entity", "community", "fact"]` (drop `episode` from default). Keep all types in `GraphControlPanel` toggles for power-user access.

2. **NodeDetailPopover enhancement** (medium): When clicking a P/F/D node, the sidebar shows:
   - Current: name, confidence, connections, tags, approve/reject (principles only)
   - New: "Related Context" section showing linked Insights, Observations, and Research chunks (query by `references` + shared tags, limit 5)
   - New: "Feedback" section — a single-line text input + send button that creates a `NodeFeedback` record

3. **NodeFeedback model + API** (medium):
   ```python
   # New: hestia/research/feedback.py
   @dataclass
   class NodeFeedback:
       id: str
       node_id: str
       node_type: str
       feedback_text: str  # Raw conversational input
       parsed_intent: Optional[str]  # LLM-extracted: "merge", "outdated", "correct", "adjust", "relate"
       parsed_target: Optional[str]  # Referenced node/concept if any
       status: str  # "pending" | "processed" | "applied"
       created_at: datetime
   ```
   - `POST /v1/research/nodes/{node_id}/feedback` — store feedback
   - `GET /v1/research/feedback/pending` — list unprocessed feedback

4. **Nightly feedback processor** (medium): New LearningScheduler monitor:
   - Runs nightly (add to `learning/scheduler.py`)
   - Gathers all `status=pending` feedback
   - LLM batch-processes: parse intent, identify merge targets, flag contradictions
   - For high-confidence patterns (3+ feedbacks converging): propose a new Principle with `source_chunk_ids` linking the feedback + original memory chunks
   - Store proposals as PENDING principles with a `reasoning` field explaining *why* Hestia linked these memories
   - Mark feedback as `processed`
   - **Cap at 5 proposals per nightly run** to prevent principle sprawl

5. **Morning review surface** (future): Principles with reasoning show up in the graph as purple nodes. Sidebar shows the reasoning + source memories. Andrew approves/rejects. This already works — just needs the `reasoning` field displayed.

### Feature 2: Explore Navigation Cleanup

**Architecture:**

1. **macOS ExplorerView** (simple): Change `ExplorerMode` enum from `[files, inbox, resources]` to `[files, inbox]`.

2. **Files tab sub-tabs** (medium): Add an internal segmented picker inside `ExplorerFilesView`:
   ```swift
   enum FilesSubMode: String, CaseIterable {
       case filesystem = "Filesystem"
       case resources = "Resources"
   }
   ```
   - "Filesystem" shows current `ExplorerFilesView` content (breadcrumbs, file browser, preview)
   - "Resources" shows current `MacExplorerResourcesView` content (drafts, mail, tasks, notes, files aggregation)

3. **iOS unchanged** — already uses unified filter-chip view, no tabs to remove.

### Feature 3: Command Tab Modernization

#### Chat Window Simplification

1. **Remove Tia profile header (iOS + macOS):**
   - macOS: Remove `FloatingAvatarView` from `MacChatPanelView`. Mode switching moves to a compact pill/dropdown in the input bar area.
   - iOS: Remove `header` computed property from `ChatView`. Mode switching moves to input bar. Remove `avatarPosition` state and ripple effect (or re-anchor ripple to input bar).
   - Session management (new conversation) moves to a toolbar icon or Cmd+N shortcut.

2. **Redesigned input bar (reference: Cursor + VS Code agent):**
   ```
   +---------------------------------------------+
   | [Mode v]  Message Hestia...          [L] [>] |
   +---------------------------------------------+
   ```
   - Mode selector: compact dropdown/pill at input-bar left (replaces header)
   - Private lock: small toggle icon (existing, just repositioned)
   - Send/mic: right-aligned (existing behavior)
   - Multi-line expansion: keep macOS CLITextView behavior, add to iOS
   - **No header. No avatar. No greeting.** The chat messages ARE the interface.

3. **Session management:**
   - New session: Cmd+N / toolbar icon, not in-chat header
   - Session history: accessible via sidebar or menu, not inline

#### Orders Under System (Wizard Redesign)

1. **Navigation:** Remove Orders from wherever it currently sits as a standalone widget. Orders lives under **System -> Active Workflows** (already partially there in `SystemActivityView`).

2. **List View — Past/Upcoming split:**
   - Upcoming: active orders sorted by next execution time. Recurring indicator.
   - Past: recent executions sorted by timestamp DESC. Success/failure indicator.
   - Tap an order -> detail view with full execution history.

3. **Setup/Edit Wizard (3-step):**

   **Step 1: Draft the Prompt**
   - Large TextEditor for the order prompt (what should Hestia do?)
   - Template suggestions (e.g., "Morning briefing", "Portfolio check", "Research digest")
   - Preview of how Hestia will interpret the prompt (optional: quick LLM parse)

   **Step 2: Connect the Resources**
   - Grid of available MCPResource toggles (existing 9 resources as selectable cards)
   - Show which resources are relevant to the prompt (auto-suggest based on step 1)
   - Minimum 1 required

   **Step 3: Set the Schedule**
   - Frequency picker: Once, Daily, Weekly, Monthly, Custom
   - Time picker
   - Day-of-week selector (for weekly)
   - Preview: "Runs every Monday at 8:00 AM" natural language summary
   - Create / Save button

   Wizard state preserved across steps. Back button to revise. Validation on final step.

### Updated Effort Estimates

| Work Item | Hours | Sprint Fit |
|-----------|-------|------------|
| **Graph View** | | |
| Graph default filter change | 1h | Quick win |
| NodeDetailPopover "Related Context" section | 3h | Medium |
| NodeFeedback model + API endpoint | 3h | Medium |
| Mini-chat input in NodeDetailPopover (Swift) | 4h | Medium |
| Nightly feedback processor (LearningScheduler) | 6h | Medium |
| Reasoning display in principle sidebar | 2h | Quick win |
| **Explore Nav** | | |
| Remove Resources tab, add Files sub-tabs | 4h | Medium |
| **Command Tab** | | |
| Remove Tia header (iOS + macOS) | 2h | Quick win |
| Redesign input bar (mode pill + compact controls) | 5h | Medium |
| Session management relocation | 2h | Quick win |
| Orders: Past/Upcoming list view | 4h | Medium |
| Orders: 3-step Setup/Edit Wizard | 8h | Large |
| Orders: Move under System section | 2h | Quick win |
| **Total** | **~46h** | **3-4 week span** |

### Suggested Sprint Breakdown (Revised)

**Sprint A (~14h): UI Cleanup + Quick Wins**
- Remove Tia header (iOS + macOS)
- Graph default filter change
- Explore nav restructure (Files sub-tabs)
- Orders: move under System section
- Session management relocation
- Reasoning display for principles

**Sprint B (~15h): Chat + Graph Depth**
- Redesign input bar (mode pill, compact controls, Cursor-inspired)
- NodeDetailPopover "Related Context" section
- NodeFeedback model + API
- Mini-chat input in NodeDetailPopover

**Sprint C (~17h): Orders Wizard + Feedback Loop**
- Orders: Past/Upcoming list view
- Orders: 3-step Setup/Edit Wizard
- Nightly feedback processor
- Integration testing across all features

## Final Critiques

**The Skeptic — "Why won't this work?"**
Conversational feedback parsing is the riskiest piece. If the LLM misinterprets "this is wrong" as "delete this" vs. "this needs correction," you get bad Principle proposals. **Mitigation:** Start with a narrow intent taxonomy (merge, outdated, correct, relate, delete) and use structured extraction with examples. Fallback: store raw feedback for manual review if confidence < 0.7. Also: removing the chat header risks making mode switching less discoverable for first-time users. **Mitigation:** The mode pill in the input bar is always visible — higher visibility than a header dropdown that requires looking up.

**The Pragmatist — "Is the effort worth it?"**
46 hours across 3 sprints is substantial but each sprint delivers standalone value. Sprint A (14h) delivers immediate UX improvements with zero backend changes. Sprint B (15h) builds the feedback infrastructure. Sprint C (17h) is the most speculative (orders wizard) — could be deferred without losing the other value. **Verdict:** Worth it. Sprint A alone justifies the effort. Sprint B creates the compounding value. Sprint C is optional enhancement.

**The Long-Term Thinker — "What happens in 6 months?"**
The feedback loop creates a virtuous cycle: more feedback -> better Principles -> more trust in the graph -> more feedback. Risk: if Andrew stops reviewing Principles, PENDING items accumulate. **Mitigation:** Add a "stale principle" threshold — if >10 PENDING principles exist for >7 days, Hestia nudges via notification relay (Sprint 20C infrastructure). The Explore nav change and header removal are permanent simplifications — zero maintenance cost. The orders wizard is a one-time build that replaces an inferior UX. The moonshot spatial canvas (SHELVED) becomes viable after WWDC 2026 SwiftUI improvements and M5 Ultra hardware.

## Open Questions

1. **Feedback batch size:** Should the nightly processor handle all pending feedback, or cap at 5 items per run to keep inference costs bounded? (Recommendation: cap at 5, process oldest first.)
2. **Principle reasoning UX:** Should reasoning show inline in the sidebar, or as an expandable disclosure group? (Recommendation: expandable disclosure — keeps the sidebar compact by default.)
3. **Merge proposals:** When feedback suggests merging two P/F/D nodes, should Hestia auto-merge on approval or present the merged version as a new PENDING principle for review? (Recommendation: new PENDING principle — safer, preserves originals.)
4. **Resources sub-tab default:** Should Files default to "Filesystem" or "Resources" sub-tab? (Recommendation: Filesystem — it's the primary use case.)
5. **Greeting preservation:** Should the "Morning, Boss." greeting survive somewhere (e.g., first message of a new session, daily briefing card) or be removed entirely? (Recommendation: move to first message of new session — preserves personality without wasting header space.)
6. **iOS ripple effect:** Remove the mode-switch ripple entirely, or re-anchor it to the input bar mode pill? (Recommendation: remove — it's a visual flourish with no functional purpose.)
7. **Orders wizard vs. defer:** Should Sprint C's orders wizard (8h) be built now or deferred until orders see more usage? (Recommendation: defer if time-constrained — current inline form works.)

## Sources

- [InfraNodus: Visualize PKM Knowledge Graphs](https://infranodus.com/use-case/visualize-knowledge-graphs-pkm)
- [Mem0: Knowledge Graph Memory for Enterprise AI](https://mem0.ai/blog/mcp-knowledge-graph-memory-enterprise-ai)
- [Semantic Zooming for Ontology Graph Visualizations (ACM)](https://dl.acm.org/doi/10.1145/3148011.3148015)
- [ChatGPT Pulse: Proactive AI Briefings (OpenAI)](https://openai.com/index/introducing-chatgpt-pulse/)
- [ChatGPT Pulse Makes AI Your Personal Research Assistant While You Sleep](https://www.theneuron.ai/explainer-articles/chatgpt-pulse-makes-ai-your-personal-research-assistant-while-you-sleep)
- [AI Memory Explained: Perplexity, ChatGPT, Pieces, Claude](https://pieces.app/blog/types-of-ai-memory)
- [Atlas: Knowledge Graph Tools Compared (2026)](https://www.atlasworkspace.ai/blog/knowledge-graph-tools)
- [Cursor Features](https://cursor.com/features)
- [Cursor Layout and UI Feedback Megathread](https://forum.cursor.com/t/megathread-cursor-layout-and-ui-feedback/146790)
- [VS Code Copilot Agents Overview](https://code.visualstudio.com/docs/copilot/agents/overview)
- [GitHub Copilot in VS Code v1.110 — February 2026 Release](https://github.blog/changelog/2026-03-06-github-copilot-in-visual-studio-code-v1-110-february-release/)
- [Agents Took Over VS Code in 2025](https://visualstudiomagazine.com/articles/2025/11/05/microsoft-details-how-agents-took-over-vs-code-in-2025.aspx)
- [2026 UI/UX Trends for AI-Powered Applications](https://vocal.media/01/best-ui-ux-trends-for-ai-powered-applications-in-2026)
- [Multi-Step Form Best Practices (Growform)](https://www.growform.co/must-follow-ux-best-practices-when-designing-a-multi-step-form/)
- [Multi-Step Forms vs Single-Step: Which Converts Better? (IvyForms)](https://ivyforms.com/blog/multi-step-forms-single-step-forms/)
- [8 Best Multi-Step Form Examples 2025 (WebStacks)](https://www.webstacks.com/blog/multi-step-form)
- [KONDA: Semantic Annotation with Human-in-the-Loop (SCI-K 2025)](https://sci-k.github.io/2025/papers/paper14.pdf)
- [Knowledge Graph Construction with LLMs (Nature Scientific Reports 2026)](https://www.nature.com/articles/s41598-026-38066-w)
- [The End of Forgetting: Limitless, Rewind, and Personal Knowledge AI (2025)](https://asktodo.ai/blog/ai-memory-assistants-limitless-rewind-trends-2025)
- [From LLMs to Knowledge Graphs: Production-Ready Systems 2025](https://medium.com/@claudiubranzan/from-llms-to-knowledge-graphs-building-production-ready-graph-systems-in-2025-2b4aff1ec99a)
