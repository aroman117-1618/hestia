# Workflow Prompt Refine Button — Design Spec

**Date:** 2026-03-28
**Status:** Approved
**Scope:** Backend endpoint + macOS Node Inspector UI

---

## Summary

Add a "Refine" button to the Node Inspector's prompt editor that generates 2-3 improved prompt variations using local inference with full personal context. The user picks a variation to apply (or dismisses). Refinement always runs locally — nothing leaves the device — so the full user profile and memory are available to personalize suggestions.

## Motivation

Workflow prompts run unattended. Subtle phrasing issues compound at execution time (e.g., a vague prompt triggering a full codebase glob that blows the context window). Users write prompts conversationally, but LLMs respond better to structured, scoped instructions. The Refine button bridges this gap while teaching better prompt engineering over time.

## Architecture

### Data Flow

```
User Prompt + Personal Context → Local LLM → 2-3 Variations
```

**Inputs:**
- `prompt` (str): The raw prompt from the node config
- `inference_route` (str): The node's target model ("local", "smart_cloud", "full_cloud")
- Personal context (loaded server-side):
  - Full user profile (all tiers — IDENTITY, MIND, TOOLS, BODY, SPIRIT, VITALS, MEMORY)
  - Relevant memory chunks (top-5 via memory search on the prompt)

**Outputs:**
- 2-3 `PromptVariation` objects, each with:
  - `label` (str): Strategy name — e.g., "Focused", "Thorough", "Structured"
  - `prompt` (str): The refined prompt text
  - `explanation` (str): Why this refinement was chosen, what changed
  - `model_suitability` (str): "cloud_optimized" | "local_friendly" | "universal"

### Privacy Constraint

Refinement **always runs on the local model** (`force_local=True`). This is non-negotiable. The full user profile (including IDENTITY and BODY, which are excluded from cloud contexts via `get_cloud_safe_context()`) is injected because the inference never leaves the device.

### Inference Strategy

- Uses the PRIMARY model tier (Qwen 3.5 9B) via `InferenceClient.complete(force_tier="primary")`
- System prompt instructs the model to:
  1. Analyze the raw prompt for weaknesses (vague scope, missing output format, context overflow risk)
  2. Consider the target inference route when shaping variations (cloud = richer/longer, local = concise/constrained)
  3. Personalize using the user's profile and memory (reference specific preferences, projects, priorities)
  4. Return exactly 2-3 variations with labels, explanations, and model suitability tags
- Response format: JSON (parsed server-side, fallback to single "improved" variation if parse fails)

## Backend

### New Endpoint

```
POST /v1/workflows/refine-prompt
```

**Request body (Pydantic schema):**
```python
class RefinePromptRequest(BaseModel):
    prompt: str                    # The raw prompt to refine
    inference_route: str = ""      # Node's target: "local", "smart_cloud", "full_cloud"
```

**Response body:**
```python
class PromptVariation(BaseModel):
    label: str                     # "Focused", "Thorough", "Structured"
    prompt: str                    # The refined prompt text
    explanation: str               # What changed and why
    model_suitability: str         # "cloud_optimized", "local_friendly", "universal"

class RefinePromptResponse(BaseModel):
    variations: List[PromptVariation]
    context_used: List[str]        # Which context sources were used (for transparency)
```

**Implementation location:** `hestia/api/routes/workflows.py` (new route in existing router)

**Handler logic:**
1. Load user profile context via `get_user_config_loader()` (all tiers — safe because local-only)
2. Search memory for top-5 relevant chunks via `MemoryManager.search(prompt)`
3. Build system prompt with refinement instructions + personal context + inference route
4. Call `InferenceClient.complete(force_tier="primary", format="json")` to ensure local-only inference
5. Parse response into `PromptVariation` list
6. Fallback: if JSON parsing fails, return single variation with the raw improved text

### System Prompt Template

The refinement system prompt should:
- Identify prompt weaknesses (vague scope, missing structure, context overflow risk)
- Generate 2-3 variations with different strategies
- Factor in the target model (cloud has 200K context, local has 32K)
- Personalize using injected profile/memory context
- Return structured JSON

### Error Handling

- Local model unavailable: Return 503 with message "Refinement requires local inference"
- Empty prompt: Return 400
- Parse failure: Return single variation with best-effort text extraction
- Timeout: 30s max (local inference can be slow on complex prompts)

## macOS UI

### Node Inspector Changes (`MacNodeInspectorView.swift`)

**New state:**
```swift
@State private var isRefining: Bool = false
@State private var refineVariations: [PromptVariation] = []
@State private var showRefinePanel: Bool = false
```

**Refine button:** Placed directly below the prompt TextEditor, before the Inference picker.
- SF Symbol: `wand.and.stars`
- Amber accent color (matches Hestia design system)
- Label: "Refine" with subtle "Local" indicator
- Disabled while `isRefining` (shows spinner)

**Slide-out panel:** Appears to the right of or below the inspector when variations are returned.
- Header: "Refined Variations" with dismiss (x) button
- Each variation is a card showing:
  - Label (bold, e.g., "Focused")
  - Model suitability tag (colored badge: green for cloud-optimized, amber for local-friendly, gray for universal)
  - Refined prompt text (truncated with expand)
  - Explanation in italic
  - "Apply" button
- Clicking "Apply" replaces the prompt text in the editor, closes the panel
- Panel is non-destructive: original prompt preserved until Apply is clicked
- Applying a variation does NOT auto-save — user still clicks existing Save button

### New API Model (`APIModels.swift` or `WorkflowModels.swift`)

```swift
struct PromptVariation: Codable, Identifiable {
    var id: String { label }
    let label: String
    let prompt: String
    let explanation: String
    let modelSuitability: String
}

struct RefinePromptResponse: Codable {
    let variations: [PromptVariation]
    let contextUsed: [String]
}
```

### APIClient Extension

```swift
func refinePrompt(_ prompt: String, inferenceRoute: String) async throws -> RefinePromptResponse
```

Calls `POST /v1/workflows/refine-prompt`.

## Testing

### Backend Tests (`tests/test_workflow_routes.py` or new `tests/test_workflow_refine.py`)

1. **Happy path**: Mock inference client, verify 2-3 variations returned with correct schema
2. **Empty prompt**: Returns 400
3. **JSON parse failure fallback**: Mock inference returning non-JSON, verify single variation extracted
4. **Personal context loading**: Verify user profile and memory are loaded (mock both managers)
5. **Force local**: Verify `force_tier="primary"` is passed to inference client

### macOS UI (Manual Verification)

1. Refine button visible only on `run_prompt` nodes
2. Spinner shown during inference
3. Panel displays variations with correct labels and tags
4. Apply replaces prompt text
5. Dismiss closes panel without changes
6. Save still required after Apply

## Scope Boundaries

**In scope:**
- Backend refinement endpoint with personal context
- macOS Node Inspector slide-out panel
- Model suitability tagging based on inference route

**Out of scope (future):**
- iOS support (no workflow canvas on iOS yet)
- Refinement history / undo stack beyond single undo
- Auto-refine on save
- Custom refinement strategies / user-defined variation labels
- React Flow canvas integration (inspector is SwiftUI-native)
