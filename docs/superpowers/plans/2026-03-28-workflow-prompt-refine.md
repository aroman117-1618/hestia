# Workflow Prompt Refine Button — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Refine" button to the macOS Node Inspector that generates 2-3 personalized prompt variations using local-only inference with full user context.

**Architecture:** New `POST /v1/workflows/refine-prompt` endpoint loads user profile + memory, calls local inference with a refinement system prompt, returns structured variations. macOS side adds a Refine button to `MacNodeInspectorView` that shows a slide-out panel with variation cards.

**Tech Stack:** Python/FastAPI (backend), SwiftUI (macOS), Pydantic schemas, local Ollama inference

**Spec:** `docs/superpowers/specs/2026-03-28-workflow-prompt-refine-design.md`

---

### Task 1: Backend — Pydantic Schemas and Endpoint Stub

**Files:**
- Modify: `hestia/api/routes/workflows.py` (add schemas + route)
- Test: `tests/test_workflow_refine.py` (new file)

- [ ] **Step 1: Write the failing test for the endpoint schema validation**

Create `tests/test_workflow_refine.py`:

```python
"""Tests for the workflow prompt refinement endpoint."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from hestia.workflows.database import WorkflowDatabase
from hestia.workflows.event_bus import WorkflowEventBus
from hestia.workflows.executor import DAGExecutor
from hestia.workflows.manager import WorkflowManager


@pytest_asyncio.fixture
async def manager(tmp_path: Path):
    db = WorkflowDatabase(tmp_path / "test_refine.db")
    await db.connect()
    event_bus = WorkflowEventBus()
    executor = DAGExecutor(event_bus=event_bus, node_timeout=5)
    mgr = WorkflowManager(database=db, executor=executor, event_bus=event_bus)
    yield mgr
    await db.close()


@pytest_asyncio.fixture
async def client(manager: WorkflowManager):
    from hestia.api.routes.workflows import router
    from hestia.api.middleware.auth import get_device_token
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_device_token] = lambda: "test-token"

    with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=manager):
        with patch("hestia.api.routes.workflows.get_workflow_scheduler") as mock_sched:
            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_workflow = lambda wf: None
            mock_scheduler.unschedule_workflow = lambda wf_id: None
            mock_sched.return_value = mock_scheduler
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                yield c


class TestRefinePromptEndpoint:
    @pytest.mark.asyncio
    async def test_empty_prompt_returns_400(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/workflows/refine-prompt",
            json={"prompt": "", "inference_route": "full_cloud"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_prompt_returns_422(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/workflows/refine-prompt",
            json={"inference_route": "full_cloud"},
        )
        assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workflow_refine.py -v --timeout=30`
Expected: FAIL — endpoint does not exist (404)

- [ ] **Step 3: Add schemas and endpoint stub to workflows.py**

Add to the schemas section of `hestia/api/routes/workflows.py`:

```python
class RefinePromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    inference_route: str = Field("", pattern="^(|local|smart_cloud|full_cloud)$")


class PromptVariationSchema(BaseModel):
    label: str
    prompt: str
    explanation: str
    model_suitability: str


class RefinePromptResponse(BaseModel):
    variations: List[PromptVariationSchema]
    context_used: List[str]
```

Add the endpoint after the existing routes (before the SSE stream endpoint):

```python
@router.post("/refine-prompt")
async def refine_prompt(
    request: RefinePromptRequest,
    _token: str = Depends(get_device_token),
) -> JSONResponse:
    """Refine a workflow prompt using local inference with personal context."""
    if not request.prompt.strip():
        return JSONResponse(status_code=400, content={"error": "Prompt cannot be empty"})

    # Stub — will be implemented in Task 2
    return JSONResponse(
        status_code=501,
        content={"error": "Not yet implemented"},
    )
```

- [ ] **Step 4: Run tests to verify schema validation works**

Run: `python -m pytest tests/test_workflow_refine.py -v --timeout=30`
Expected: `test_empty_prompt_returns_400` PASSES, `test_missing_prompt_returns_422` PASSES

- [ ] **Step 5: Commit**

```bash
git add hestia/api/routes/workflows.py tests/test_workflow_refine.py
git commit -m "feat(workflows): add refine-prompt endpoint stub with schema validation"
```

---

### Task 2: Backend — Refinement Logic with Personal Context

**Files:**
- Modify: `hestia/api/routes/workflows.py` (implement endpoint body)
- Test: `tests/test_workflow_refine.py` (add happy path + fallback tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_workflow_refine.py`:

```python
class TestRefinePromptLogic:
    @pytest.mark.asyncio
    async def test_happy_path_returns_variations(self, client: AsyncClient) -> None:
        """Mock inference to return valid JSON, verify structured response."""
        mock_inference_response = MagicMock()
        mock_inference_response.content = json.dumps({
            "variations": [
                {
                    "label": "Focused",
                    "prompt": "Audit the top 5 issues in security and performance.",
                    "explanation": "Scoped to actionable items.",
                    "model_suitability": "cloud_optimized",
                },
                {
                    "label": "Structured",
                    "prompt": "Report findings as JSON with severity scores.",
                    "explanation": "Machine-parseable output.",
                    "model_suitability": "local_friendly",
                },
            ]
        })

        mock_user_config = MagicMock()
        mock_user_config.context_block = "## User Profile\n\nAndrew is a software engineer."
        mock_user_config.get_topic_context.return_value = ""

        mock_loader = AsyncMock()
        mock_loader.load.return_value = mock_user_config

        mock_memory_results = [
            MagicMock(content="Andrew prioritizes security and performance."),
        ]

        with patch("hestia.api.routes.workflows.get_user_config_loader", return_value=mock_loader), \
             patch("hestia.api.routes.workflows.get_memory_manager") as mock_mem_factory, \
             patch("hestia.api.routes.workflows.get_inference_client") as mock_inf_factory:
            mock_mem = AsyncMock()
            mock_mem.search.return_value = mock_memory_results
            mock_mem_factory.return_value = mock_mem

            mock_inference = AsyncMock()
            mock_inference.complete.return_value = mock_inference_response
            mock_inf_factory.return_value = mock_inference

            response = await client.post(
                "/v1/workflows/refine-prompt",
                json={
                    "prompt": "Hunt through the codebase for issues",
                    "inference_route": "full_cloud",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "variations" in data
        assert len(data["variations"]) == 2
        assert data["variations"][0]["label"] == "Focused"
        assert "context_used" in data
        assert "user_profile" in data["context_used"]
        assert "memory" in data["context_used"]

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_single_variation(self, client: AsyncClient) -> None:
        """When local model returns non-JSON, fall back to single variation."""
        mock_inference_response = MagicMock()
        mock_inference_response.content = "Here is an improved prompt: Analyze the codebase systematically."

        mock_user_config = MagicMock()
        mock_user_config.context_block = ""
        mock_user_config.get_topic_context.return_value = ""

        mock_loader = AsyncMock()
        mock_loader.load.return_value = mock_user_config

        with patch("hestia.api.routes.workflows.get_user_config_loader", return_value=mock_loader), \
             patch("hestia.api.routes.workflows.get_memory_manager") as mock_mem_factory, \
             patch("hestia.api.routes.workflows.get_inference_client") as mock_inf_factory:
            mock_mem = AsyncMock()
            mock_mem.search.return_value = []
            mock_mem_factory.return_value = mock_mem

            mock_inference = AsyncMock()
            mock_inference.complete.return_value = mock_inference_response
            mock_inf_factory.return_value = mock_inference

            response = await client.post(
                "/v1/workflows/refine-prompt",
                json={"prompt": "Do something useful"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["variations"]) == 1
        assert data["variations"][0]["label"] == "Improved"
        assert "Analyze the codebase" in data["variations"][0]["prompt"]

    @pytest.mark.asyncio
    async def test_force_tier_primary_used(self, client: AsyncClient) -> None:
        """Verify refinement always uses force_tier='primary' (local only)."""
        mock_inference_response = MagicMock()
        mock_inference_response.content = json.dumps({"variations": [{
            "label": "Test", "prompt": "test", "explanation": "test",
            "model_suitability": "universal",
        }]})

        mock_user_config = MagicMock()
        mock_user_config.context_block = ""
        mock_user_config.get_topic_context.return_value = ""
        mock_loader = AsyncMock()
        mock_loader.load.return_value = mock_user_config

        with patch("hestia.api.routes.workflows.get_user_config_loader", return_value=mock_loader), \
             patch("hestia.api.routes.workflows.get_memory_manager") as mock_mem_factory, \
             patch("hestia.api.routes.workflows.get_inference_client") as mock_inf_factory:
            mock_mem = AsyncMock()
            mock_mem.search.return_value = []
            mock_mem_factory.return_value = mock_mem

            mock_inference = AsyncMock()
            mock_inference.complete.return_value = mock_inference_response
            mock_inf_factory.return_value = mock_inference

            await client.post(
                "/v1/workflows/refine-prompt",
                json={"prompt": "Test prompt", "inference_route": "full_cloud"},
            )

            # Verify force_tier="primary" was passed
            call_kwargs = mock_inference.complete.call_args
            assert call_kwargs.kwargs.get("force_tier") == "primary" or \
                   (len(call_kwargs.args) > 0 and "force_tier" in str(call_kwargs))

    @pytest.mark.asyncio
    async def test_inference_unavailable_returns_503(self, client: AsyncClient) -> None:
        """When local model is down, return 503."""
        mock_user_config = MagicMock()
        mock_user_config.context_block = ""
        mock_user_config.get_topic_context.return_value = ""
        mock_loader = AsyncMock()
        mock_loader.load.return_value = mock_user_config

        with patch("hestia.api.routes.workflows.get_user_config_loader", return_value=mock_loader), \
             patch("hestia.api.routes.workflows.get_memory_manager") as mock_mem_factory, \
             patch("hestia.api.routes.workflows.get_inference_client") as mock_inf_factory:
            mock_mem = AsyncMock()
            mock_mem.search.return_value = []
            mock_mem_factory.return_value = mock_mem

            mock_inference = AsyncMock()
            mock_inference.complete.side_effect = Exception("Connection refused")
            mock_inf_factory.return_value = mock_inference

            response = await client.post(
                "/v1/workflows/refine-prompt",
                json={"prompt": "Test prompt"},
            )

        assert response.status_code == 503
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workflow_refine.py::TestRefinePromptLogic -v --timeout=30`
Expected: All FAIL (endpoint returns 501 stub)

- [ ] **Step 3: Implement the endpoint**

Replace the stub in `hestia/api/routes/workflows.py`. Add these imports at the top of the file:

```python
from hestia.user.config_loader import get_user_config_loader
from hestia.user.config_models import UserConfigFile
from hestia.memory.manager import get_memory_manager
from hestia.inference import InferenceClient
```

Add a helper to get the inference client singleton:

```python
async def get_inference_client() -> InferenceClient:
    """Get inference client singleton for refinement."""
    return InferenceClient()
```

Replace the endpoint stub:

```python
_REFINE_SYSTEM_PROMPT = """\
You are a prompt engineering expert for Hestia, a personal AI assistant.

Your task: take the user's raw workflow prompt and produce 2-3 improved variations.

## Context About the User
{user_context}

## Relevant Memories
{memory_context}

## Target Inference
The prompt will execute on: {inference_target}
- "local" = Qwen 3.5 9B, 32K context — keep prompts concise, structured, avoid broad file scanning
- "smart_cloud" = local-first with cloud fallback — moderate complexity is fine
- "full_cloud" = Anthropic/OpenAI, 200K context — can handle rich, detailed prompts

## Instructions
1. Analyze the prompt for: vague scope, missing output format, context overflow risk, missed personalization opportunities
2. Generate 2-3 variations with different strategies (e.g., Focused, Thorough, Structured)
3. For each variation, consider the user's priorities, projects, and preferences from the context above
4. Tag each with model_suitability: "cloud_optimized", "local_friendly", or "universal"

Return ONLY valid JSON in this exact format:
{{"variations": [
  {{"label": "...", "prompt": "...", "explanation": "...", "model_suitability": "..."}},
  ...
]}}"""


@router.post("/refine-prompt")
async def refine_prompt(
    request: RefinePromptRequest,
    _token: str = Depends(get_device_token),
) -> JSONResponse:
    """Refine a workflow prompt using local inference with personal context."""
    if not request.prompt.strip():
        return JSONResponse(status_code=400, content={"error": "Prompt cannot be empty"})

    context_used: List[str] = []

    # Load full user profile (safe — local inference only)
    user_context = ""
    try:
        loader = await get_user_config_loader()
        user_config = await loader.load()
        user_context = user_config.context_block
        # Add topic files for richer context
        topic_ctx = user_config.get_topic_context([
            UserConfigFile.BODY, UserConfigFile.SPIRIT, UserConfigFile.VITALS,
        ])
        if topic_ctx:
            user_context = f"{user_context}\n\n{topic_ctx}" if user_context else topic_ctx
        if user_context:
            context_used.append("user_profile")
    except Exception as e:
        logger.warning(
            f"Failed to load user profile for refinement: {type(e).__name__}",
            component=LogComponent.WORKFLOW,
        )

    # Search memory for relevant context
    memory_context = ""
    try:
        mem_manager = await get_memory_manager()
        results = await mem_manager.search(request.prompt, limit=5)
        if results:
            memory_context = "\n".join(
                f"- {r.content}" for r in results
            )
            context_used.append("memory")
    except Exception as e:
        logger.warning(
            f"Failed to search memory for refinement: {type(e).__name__}",
            component=LogComponent.WORKFLOW,
        )

    # Build system prompt
    inference_target = request.inference_route or "smart_cloud"
    system = _REFINE_SYSTEM_PROMPT.format(
        user_context=user_context or "(No user profile loaded)",
        memory_context=memory_context or "(No relevant memories found)",
        inference_target=inference_target,
    )

    # Call local inference
    try:
        inference = await get_inference_client()
        response = await inference.complete(
            prompt=f"Refine this workflow prompt:\n\n{request.prompt}",
            system=system,
            force_tier="primary",
            format="json",
            temperature=0.7,
            max_tokens=2048,
        )
    except Exception as e:
        logger.error(
            f"Refinement inference failed: {type(e).__name__}",
            component=LogComponent.WORKFLOW,
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Refinement requires local inference", "detail": type(e).__name__},
        )

    # Parse response
    import json as json_mod
    variations = []
    try:
        parsed = json_mod.loads(response.content)
        raw_variations = parsed.get("variations", [])
        for v in raw_variations:
            variations.append({
                "label": v.get("label", "Improved"),
                "prompt": v.get("prompt", ""),
                "explanation": v.get("explanation", ""),
                "model_suitability": v.get("model_suitability", "universal"),
            })
    except (json_mod.JSONDecodeError, KeyError, TypeError):
        # Fallback: treat entire response as single improved prompt
        variations.append({
            "label": "Improved",
            "prompt": response.content.strip(),
            "explanation": "Direct refinement from local model.",
            "model_suitability": "universal",
        })

    if not variations:
        variations.append({
            "label": "Improved",
            "prompt": request.prompt,
            "explanation": "No refinements generated.",
            "model_suitability": "universal",
        })

    return JSONResponse(content={
        "variations": variations,
        "context_used": context_used,
    })
```

- [ ] **Step 4: Run all refine tests**

Run: `python -m pytest tests/test_workflow_refine.py -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Run full workflow test suite to verify no regressions**

Run: `python -m pytest tests/ -k "workflow" -v --timeout=30`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add hestia/api/routes/workflows.py tests/test_workflow_refine.py
git commit -m "feat(workflows): implement refine-prompt endpoint with personal context"
```

---

### Task 3: macOS — API Model and Client Extension

**Files:**
- Modify: `HestiaApp/macOS/Services/APIClient+Workflows.swift` (add refine method)
- Create: `HestiaApp/Shared/Models/PromptVariation.swift` (response model)

- [ ] **Step 1: Create the PromptVariation model**

Create `HestiaApp/Shared/Models/PromptVariation.swift`:

```swift
import Foundation

struct PromptVariation: Codable, Identifiable {
    var id: String { label }
    let label: String
    let prompt: String
    let explanation: String
    let modelSuitability: String

    /// Human-readable suitability badge text
    var suitabilityBadge: String {
        switch modelSuitability {
        case "cloud_optimized": return "Cloud-optimized"
        case "local_friendly": return "Local-friendly"
        default: return "Universal"
        }
    }
}

struct RefinePromptRequest: Codable {
    let prompt: String
    let inferenceRoute: String

    enum CodingKeys: String, CodingKey {
        case prompt
        case inferenceRoute = "inference_route"
    }
}

struct RefinePromptResponse: Codable {
    let variations: [PromptVariation]
    let contextUsed: [String]

    enum CodingKeys: String, CodingKey {
        case variations
        case contextUsed = "context_used"
    }
}
```

- [ ] **Step 2: Add refinePrompt to APIClient+Workflows.swift**

Add to `HestiaApp/macOS/Services/APIClient+Workflows.swift`, after the `patchNode` method:

```swift
    // MARK: - Prompt Refinement

    func refinePrompt(_ prompt: String, inferenceRoute: String) async throws -> RefinePromptResponse {
        let request = RefinePromptRequest(prompt: prompt, inferenceRoute: inferenceRoute)
        return try await post("/workflows/refine-prompt", body: request)
    }
```

- [ ] **Step 3: Add PromptVariation.swift to project.yml targets**

Check `HestiaApp/project.yml` to verify that `Shared/Models/` is already included in the macOS target's sources. If it uses a glob like `Shared/**`, no change needed. If files are listed explicitly, add:

```yaml
- path: Shared/Models/PromptVariation.swift
```

- [ ] **Step 4: Verify build compiles**

Run: `cd HestiaApp && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5`
Expected: `BUILD SUCCEEDED`

- [ ] **Step 5: Commit**

```bash
git add HestiaApp/Shared/Models/PromptVariation.swift HestiaApp/macOS/Services/APIClient+Workflows.swift
git commit -m "feat(macos): add PromptVariation model and refinePrompt API client method"
```

---

### Task 4: macOS — Refine Button and Slide-Out Panel in Node Inspector

**Files:**
- Modify: `HestiaApp/macOS/Views/Workflow/MacNodeInspectorView.swift`

- [ ] **Step 1: Add state properties**

Add to the existing `@State` block at the top of `MacNodeInspectorView`:

```swift
    // refine
    @State private var isRefining: Bool = false
    @State private var refineVariations: [PromptVariation] = []
    @State private var showRefinePanel: Bool = false
    @State private var refineError: String?
```

- [ ] **Step 2: Add the Refine button below the prompt TextEditor**

In the `configSection` computed property, inside the `.runPrompt` case, add after the prompt `fieldGroup` closing brace (after the `.overlay(RoundedRectangle...)` block) and before `fieldGroup("Inference")`:

```swift
            // Refine button
            HStack(spacing: MacSpacing.xs) {
                Button {
                    Task { await refineCurrentPrompt() }
                } label: {
                    HStack(spacing: 4) {
                        if isRefining {
                            ProgressView()
                                .controlSize(.small)
                        } else {
                            Image(systemName: "wand.and.stars")
                                .font(.system(size: 11))
                        }
                        Text("Refine")
                            .font(MacTypography.caption)
                    }
                    .padding(.horizontal, MacSpacing.sm)
                    .padding(.vertical, 4)
                    .background(MacColors.amberAccent)
                    .foregroundStyle(MacColors.panelBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                .buttonStyle(.plain)
                .disabled(prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isRefining)
                .help("Refine prompt using local AI with your personal context")

                Text("Local")
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textTertiary)
            }
```

- [ ] **Step 3: Add the slide-out panel view**

Add a new private computed property to `MacNodeInspectorView`:

```swift
    @ViewBuilder
    private var refinePanel: some View {
        if showRefinePanel && !refineVariations.isEmpty {
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                // Header
                HStack {
                    Text("Refined Variations")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.amberAccent)
                    Spacer()
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            showRefinePanel = false
                        }
                    } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 10))
                            .foregroundStyle(MacColors.textSecondary)
                    }
                    .buttonStyle(.plain)
                }

                // Variation cards
                ForEach(refineVariations) { variation in
                    VStack(alignment: .leading, spacing: MacSpacing.xs) {
                        HStack {
                            Text(variation.label)
                                .font(MacTypography.caption.bold())
                                .foregroundStyle(MacColors.textPrimary)
                            Spacer()
                            Text(variation.suitabilityBadge)
                                .font(.system(size: 9))
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(suitabilityColor(variation.modelSuitability).opacity(0.15))
                                .foregroundStyle(suitabilityColor(variation.modelSuitability))
                                .clipShape(RoundedRectangle(cornerRadius: 3))
                        }

                        Text(variation.prompt)
                            .font(MacTypography.smallBody)
                            .foregroundStyle(MacColors.textPrimary)
                            .lineLimit(4)

                        Text(variation.explanation)
                            .font(.system(size: 10))
                            .foregroundStyle(MacColors.textTertiary)
                            .italic()

                        HStack {
                            Spacer()
                            Button("Apply") {
                                prompt = variation.prompt
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    showRefinePanel = false
                                }
                            }
                            .font(MacTypography.caption)
                            .padding(.horizontal, MacSpacing.sm)
                            .padding(.vertical, 3)
                            .background(MacColors.amberAccent)
                            .foregroundStyle(MacColors.panelBackground)
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(MacSpacing.sm)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(MacColors.cardBorder, lineWidth: 1)
                    )
                }

                if let error = refineError {
                    Text(error)
                        .font(.system(size: 10))
                        .foregroundStyle(.red)
                }
            }
            .padding(MacSpacing.sm)
            .background(MacColors.panelBackground.opacity(0.95))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(MacColors.amberAccent.opacity(0.3), lineWidth: 1)
            )
            .transition(.opacity.combined(with: .move(edge: .trailing)))
        }
    }

    private func suitabilityColor(_ suitability: String) -> Color {
        switch suitability {
        case "cloud_optimized": return .green
        case "local_friendly": return MacColors.amberAccent
        default: return MacColors.textSecondary
        }
    }
```

- [ ] **Step 4: Insert the refine panel in the body**

In the `configSection` for `.runPrompt`, add `refinePanel` after the Refine button `HStack` and before `fieldGroup("Inference")`:

```swift
            refinePanel
```

- [ ] **Step 5: Add the refineCurrentPrompt method**

Add to `MacNodeInspectorView`:

```swift
    private func refineCurrentPrompt() async {
        isRefining = true
        refineError = nil
        refineVariations = []

        do {
            let response = try await APIClient.shared.refinePrompt(
                prompt,
                inferenceRoute: inferenceRoute
            )
            refineVariations = response.variations
            withAnimation(.easeInOut(duration: 0.2)) {
                showRefinePanel = true
            }
        } catch {
            refineError = "Refinement failed — is the local model running?"
            #if DEBUG
            print("[Refine] Error: \(error)")
            #endif
        }

        isRefining = false
    }
```

- [ ] **Step 6: Verify macOS build compiles**

Run: `cd HestiaApp && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5`
Expected: `BUILD SUCCEEDED`

- [ ] **Step 7: Commit**

```bash
git add HestiaApp/macOS/Views/Workflow/MacNodeInspectorView.swift
git commit -m "feat(macos): add Refine button and slide-out variation panel to Node Inspector"
```

---

### Task 5: Integration Verification and Cleanup

**Files:**
- Modify: `hestia/api/routes/workflows.py` (update docstring endpoint count)
- Test: Run full test suite

- [ ] **Step 1: Update the module docstring endpoint count**

In `hestia/api/routes/workflows.py`, update the docstring on line 1:

```python
"""
Workflow API routes — CRUD, lifecycle, execution, refinement, SSE streaming.

16 endpoints under /v1/workflows.
"""
```

- [ ] **Step 2: Run full backend test suite**

Run: `python -m pytest tests/ -v --timeout=30 -q`
Expected: All pass (3111+ tests)

- [ ] **Step 3: Run both Xcode targets**

Run macOS:
```bash
cd HestiaApp && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5
```

Run iOS:
```bash
cd HestiaApp && xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16' build 2>&1 | tail -5
```

Expected: Both `BUILD SUCCEEDED`

- [ ] **Step 4: Commit and deploy**

```bash
git add hestia/api/routes/workflows.py
git commit -m "chore: update workflow routes docstring for refine-prompt endpoint"
```

Deploy to Mac Mini:
```bash
./scripts/deploy-to-mini.sh
```

- [ ] **Step 5: Manual smoke test**

1. Open Hestia macOS app → Orders → Self-Development workflow
2. Click a Run Prompt node to open the Node Inspector
3. Click "Refine" button
4. Verify spinner appears, then slide-out panel with 2-3 variations
5. Click "Apply" on one — verify prompt text updates
6. Dismiss without applying — verify original prompt preserved
7. Click "Save" — verify node config persists
