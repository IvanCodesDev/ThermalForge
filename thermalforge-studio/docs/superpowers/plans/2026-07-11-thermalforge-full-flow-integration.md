# ThermalForge Full-Flow Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Agent upload workflow execute through governed
thermal reasoning, curated robot-arm model artifacts, and a terminal `ready`
state using one backend.

**Architecture:** `thermalforge-api` remains the only browser-facing API. ARQ
and a managed local queue share one pipeline runner; the current LLM protocol
gains an OpenAI-compatible Responses implementation; checked-in GLBs become
task-owned, explicitly labeled reference artifacts. The Agent consumes additive
result and viewer contracts while preserving its current visual system.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, asyncio, httpx, Pydantic,
pytest, React 19, TypeScript, Vite, React Three Fiber, Vitest, Playwright.

**Commit policy:** Do not commit or push unless the user separately authorizes
that operation.

---

### Task 1: Reproduce and fix local dispatch loss

**Files:**
- Modify: `thermalforge-api/tests/test_queue.py`
- Modify: `thermalforge-api/tests/test_task_start.py`
- Modify: `thermalforge-api/app/services/queue.py`
- Modify: `thermalforge-api/app/main.py`

- [ ] **Step 1: Write the failing local queue tests**

Define a runner protocol and assert that duplicate dispatch tokens run once,
distinct tokens run independently, and `close()` observes all tasks:

```python
class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run(self, task_id: str) -> None:
        self.calls.append(task_id)


queue = InProcessTaskQueue(RecordingRunner())
await queue.enqueue_pipeline("task-1", "start:2")
await queue.enqueue_pipeline("task-1", "start:2")
await queue.close()
assert queue.runner.calls == ["task-1"]
```

Add an API-level test that posts project, task, document, and start with
`queue_enabled=False`, then waits on the task status and proves it moves beyond
`uploaded`.

- [ ] **Step 2: Run RED**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_queue.py tests/test_task_start.py -q
```

Expected: collection or assertion failure because `InProcessTaskQueue` does not
exist and local dispatch is still discarded.

- [ ] **Step 3: Implement the managed queue**

Add:

```python
class PipelineRunner(Protocol):
    async def run(self, task_id: str) -> None: ...


class InProcessTaskQueue:
    def __init__(self, runner: PipelineRunner) -> None:
        self._runner = runner
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def enqueue_pipeline(self, task_id: str, dispatch_token: str) -> None:
        dispatch_id = f"{task_id}:{dispatch_token}"
        if dispatch_id in self._tasks:
            return
        task = asyncio.create_task(self._runner.run(task_id))
        self._tasks[dispatch_id] = task
        task.add_done_callback(
            lambda completed, key=dispatch_id: self._tasks.pop(key, None)
        )

    async def healthcheck(self) -> None:
        return None

    async def close(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
```

Retain a completed-token set for the process lifetime so a repeated HTTP start
cannot rerun a dispatch after its task completes. Log background failures
without request payloads or secrets.

- [ ] **Step 4: Run GREEN**

Run the same target tests. Expected: all pass and the local API test observes a
real status transition.

---

### Task 2: Share one pipeline runner between local and ARQ

**Files:**
- Create: `thermalforge-api/app/services/pipeline.py`
- Modify: `thermalforge-api/app/workers/worker.py`
- Modify: `thermalforge-api/app/main.py`
- Modify: `thermalforge-api/tests/test_worker.py`
- Create: `thermalforge-api/tests/test_pipeline.py`

- [ ] **Step 1: Write failing runner parity tests**

Use a temporary SQLite database and fixture provider. Assert `PipelineRunner`
accepts explicit dependencies and that both `run_pipeline()` and the local queue
delegate to it.

- [ ] **Step 2: Run RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pipeline.py tests/test_worker.py -q
```

Expected: `app.services.pipeline` is missing.

- [ ] **Step 3: Extract the runner**

Create a focused class:

```python
class PipelineRunner:
    def __init__(
        self,
        *,
        database: Database,
        settings: Settings,
        artifact_store: ArtifactStore,
        ocr_provider: OcrProvider,
        llm_provider: LLMProvider,
    ) -> None: ...

    async def run(self, task_id: str) -> None:
        async with self._database.session() as session:
            # Re-read status between idempotent stages.
            ...
```

`worker.run_pipeline()` builds or receives this runner and delegates. The app
lifespan builds the same runner before choosing ARQ or in-process queue.

- [ ] **Step 4: Run GREEN**

Run target tests, then:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_queue.py tests/test_task_start.py tests/test_worker.py tests/test_pipeline.py -q
```

Expected: all pass.

---

### Task 3: Add the OpenAI-compatible structured provider

**Files:**
- Modify: `thermalforge-api/app/config.py`
- Create: `thermalforge-api/app/llm/openai_compatible.py`
- Modify: `thermalforge-api/app/llm/factory.py`
- Create: `thermalforge-api/tests/test_openai_compatible_llm.py`
- Modify: `thermalforge-api/.env.example`

- [ ] **Step 1: Write failing provider tests**

With `httpx.MockTransport`, cover:

```python
response = {
    "id": "resp-1",
    "output_text": json.dumps(valid_brief),
    "usage": {"input_tokens": 12, "output_tokens": 34},
}
```

Assert the request URL ends in `/responses`, bearer auth exists without being
returned, `model == "gpt-5.6-sol"`, output validates as the requested Pydantic
model, and malformed/empty/timeout/HTTP-error cases map to
`InvalidLLMOutput` or `LLMProviderUnavailable`.

- [ ] **Step 2: Run RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_openai_compatible_llm.py -q
```

Expected: import failure for the new provider.

- [ ] **Step 3: Implement configuration and provider**

Add settings:

```python
llm_provider: Literal["anthropic", "openai_compatible", "fixture"] = "fixture"
openai_api_key: SecretStr | None = None
openai_base_url: str = "https://api.openai.com/v1"
openai_model: str = "gpt-5.6-sol"
```

The provider sends:

```python
payload = {
    "model": self._model,
    "instructions": schema_instructions,
    "input": request.user_prompt,
    "max_output_tokens": request.max_tokens,
}
```

Parse `output_text` first, then Responses content blocks. Validate with
`request.response_model.model_validate_json(text)`. Do not include raw upstream
body text in public errors.

- [ ] **Step 4: Run GREEN**

Run provider tests and existing Anthropic/fixture tests. Expected: all pass.

---

### Task 4: Turn curated GLBs into task-owned terminal artifacts

**Files:**
- Modify: `thermalforge-api/app/config.py`
- Create: `thermalforge-api/app/services/model_completion.py`
- Modify: `thermalforge-api/app/services/pipeline.py`
- Create: `thermalforge-api/tests/test_model_completion.py`
- Modify: `thermalforge-api/tests/test_worker.py`

- [ ] **Step 1: Write failing completion tests**

Copy tiny GLB fixtures into a temporary configured model directory. Start a
fully specified text task and assert:

```python
assert task.status == "ready"
assert artifact_kinds[-2:] == ["raw_model", "normalized_model"]
assert events[-1].event_type == "task.ready"
assert normalized.metadata_json["source"] == "curated_reference"
assert normalized.metadata_json["node_names"] == ["root.0", "root.1", "root.2"]
```

Add missing-file and cancellation cases; missing seed data must produce
`failed`, not `ready`.

- [ ] **Step 2: Run RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_model_completion.py tests/test_worker.py -q
```

Expected: no model-completion service and worker still stops at
`concept_imaging`.

- [ ] **Step 3: Implement idempotent model completion**

Configure a model root and filenames. Validate resolved files remain inside the
configured root. Persist whole and segmented GLBs through `ArtifactStore`,
record approved artifacts with truthful provider/fidelity metadata, then use
legal state-machine transitions to reach `ready`.

- [ ] **Step 4: Run GREEN**

Expected: fixture worker now reaches `ready`; existing cancellation and retry
tests remain green.

---

### Task 5: Extend the viewer contract without breaking old clients

**Files:**
- Modify: `thermalforge-api/app/viewer/schemas.py`
- Modify: `thermalforge-api/app/services/viewer.py`
- Modify: `thermalforge-api/tests/test_viewer_api.py`
- Modify: `thermalforge-api/openapi.json`
- Regenerate: `thermalforge-studio/src/api/generated/*`

- [ ] **Step 1: Write failing additive-contract tests**

Assert `asset` remains the preferred segmented asset and `variants` includes
both segmented and whole variants. Assert node parts use only metadata-backed
names and model content still rejects cross-task IDs.

- [ ] **Step 2: Run RED**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_viewer_api.py -q
```

Expected: `variants` is absent.

- [ ] **Step 3: Implement schemas and mapping**

Add:

```python
class ViewerPart(BaseModel):
    id: str
    label: str
    node_names: list[str] = Field(default_factory=list)
    explode: tuple[FiniteFloat, FiniteFloat, FiniteFloat] | None = None


class ViewerVariant(BaseModel):
    id: str
    label: str
    asset: ViewerAsset
    parts: list[ViewerPart] = Field(default_factory=list)
    supports_explosion: bool = False


class ViewerManifest(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    task_id: str
    asset: ViewerAsset
    variants: list[ViewerVariant] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Regenerate and verify the contract**

Run the repository's OpenAPI export and frontend client generation scripts,
then API and OpenAPI tests. Do not hand-edit generated files.

---

### Task 6: Load real result evidence in the Agent

**Files:**
- Modify: `thermalforge-studio/src/api/workflow.ts`
- Modify: `thermalforge-studio/src/api/index.ts`
- Create: `thermalforge-studio/src/agent/taskResults.ts`
- Modify: `thermalforge-studio/src/agent/AgentExperience.tsx`
- Modify: `thermalforge-studio/src/agent/AgentHistoryDrawer.tsx`
- Modify: `thermalforge-studio/src/App.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Mock a task progressing to `ready`; assert the Agent requests engineering brief,
thermal analysis, thermal design, and viewer manifest. Open “完整过程” and assert
tabs expose factual design evidence and sanitized JSON.

- [ ] **Step 2: Run RED**

```powershell
npm test -- --run src/App.test.tsx
```

Expected: result APIs are never called and evidence tabs are absent.

- [ ] **Step 3: Implement result loading**

Use one `Promise.all` once status reaches `concept_imaging` or later. Keep result
data separate from persisted reducer state because it is derivable from the
task ID. Abort on task reset/unmount and show an actionable nonfatal error when
one result endpoint is not yet available.

- [ ] **Step 4: Run GREEN**

Expected: Agent tests pass without leaking any secret-like field.

---

### Task 7: Integrate model-viewer effects

**Files:**
- Modify: `thermalforge-studio/src/model/viewerManifest.ts`
- Modify: `thermalforge-studio/src/model/GltfViewerAsset.tsx`
- Modify: `thermalforge-studio/src/model/ModelStage.tsx`
- Modify: `thermalforge-studio/src/model/PartDetailSheet.tsx`
- Create: `thermalforge-studio/src/model/GltfViewerAsset.test.tsx`
- Modify: `thermalforge-studio/src/App.test.tsx`
- Modify: `thermalforge-studio/src/styles/agent.css`

- [ ] **Step 1: Write failing interaction tests**

Cover whole/segmented variant switch, auto-rotate, wireframe, explode, reset,
keyboard-accessible info, and generic node-part selection. Assert controls are
disabled when the chosen variant does not support them.

- [ ] **Step 2: Run RED**

```powershell
npm test -- --run src/model/GltfViewerAsset.test.tsx src/App.test.tsx
```

Expected: the new controls and variant mapping do not exist.

- [ ] **Step 3: Implement focused viewer state**

Keep UI-only model controls inside `ModelStage`. Clone imported scene materials
before wireframe/highlight mutation. Bind click selection by walking from the
event object to the nearest manifest node name. Apply explode offsets relative
to cloned original transforms and restore them exactly when disabled.

- [ ] **Step 4: Run GREEN and accessibility checks**

Expected: all model and Agent unit tests pass with semantic buttons and visible
focus states.

---

### Task 8: Add bounded no-progress reporting

**Files:**
- Modify: `thermalforge-studio/src/api/sse.ts`
- Modify: `thermalforge-studio/src/agent/AgentExperience.tsx`
- Modify: `thermalforge-studio/src/api/api.test.ts`
- Modify: `thermalforge-studio/src/App.test.tsx`

- [ ] **Step 1: Write a failing stalled-task test**

Use fake timers: SSE keepalives may maintain connection, but unchanged task
status beyond the watchdog must show “任务长时间无进展” with stop/retry actions.
Any real event or status change resets the watchdog.

- [ ] **Step 2: Run RED**

```powershell
npm test -- --run src/api/api.test.ts src/App.test.tsx
```

Expected: the UI remains indefinitely running.

- [ ] **Step 3: Implement the watchdog**

Track last progress time from actual task events/status changes, not transport
keepalives. Abort the follower before dispatching the recoverable UI error.

- [ ] **Step 4: Run GREEN**

Expected: the regression passes and normal long model requests are not timed out
as long as stage events continue.

---

### Task 9: Configure, verify, and run the full stack

**Files:**
- Modify: `thermalforge-api/.env.example`
- Modify: `docs/design.md`
- Modify: `docs/THERMALFORGE_END_TO_END_DEVELOPMENT.md`
- Local-only: `thermalforge-api/.env`

- [ ] **Step 1: Update committed configuration documentation**

Document the provider variable names with an empty key placeholder, the
in-process queue behavior, curated-model fidelity, and Redis worker mode.

- [ ] **Step 2: Run backend verification**

```powershell
.venv\Scripts\python.exe -m ruff check app tests
.venv\Scripts\python.exe -m mypy app
.venv\Scripts\python.exe -m pytest -q
```

Expected: zero failures.

- [ ] **Step 3: Run frontend verification**

```powershell
npm run lint
npm test -- --run
npm run build
npx playwright test
```

Expected: zero failures; existing low-height WebGL assertions remain green.

- [ ] **Step 4: Run fixture acceptance**

Start API and Vite, upload a small UTF-8 text document containing power,
ambient temperature, and envelope, then verify via API and browser:

```text
created -> uploaded -> parsing -> briefing -> thermal_analysis
-> concept/model stages -> ready
```

The viewer must load the task-owned GLB and the drawer must show the matching
thermal design.

- [ ] **Step 5: Run live provider acceptance**

After the user places the chosen key only in ignored
`thermalforge-api/.env`, verify the safe configuration flags without printing
the value. Restart the API with `openai_compatible`, run one bounded task, and
record whether it reaches `awaiting_input` or `ready`. If the gateway does not
support `/responses`, report the exact sanitized HTTP status and stop rather
than guessing another API shape.

- [ ] **Step 6: Final diff and secret review**

Inspect the complete diff, ensure no `.env`, bearer token, absolute user path,
temporary upload, SQLite database, generated cache, or test artifact is staged
or reported as source. Check lints on every edited file and keep both services
running for user inspection.
