# ThermalForge Agent Full-Flow Integration Design

## Goal

Keep the existing model-first Agent experience as the only frontend while making
the real upload workflow progress from document ingestion to a terminal task
state. Integrate the governed `gpt-5.6-sol` OpenAI-compatible connection and the
checked-in robot-arm GLB assets without introducing a second browser-facing
backend or restoring the removed seven-step workbench.

## Verified starting point

- `thermalforge-studio` already owns upload, task tracking, clarification, SSE,
  result-model loading, cancellation, retry, and session recovery.
- `thermalforge-api` owns the matching `/v1` task contract, document parsing,
  engineering brief generation, deterministic thermal analysis, and viewer
  artifact authorization.
- Local development currently builds `NoopTaskQueue` when Redis is disabled.
  It accepts dispatches but never executes them, leaving started uploads at
  `uploaded`.
- The worker pipeline currently ends at `concept_imaging`; it does not create a
  model artifact or transition a task to `ready`.
- The root `core` package contains an OpenAI-compatible Responses API client and
  FOC demo concepts, but it has a separate configuration, persistence model, and
  API surface. Its planned React frontend was never committed.
- The latest remote commit contains four GLB files only. They are curated
  concept meshes, not task-specific generated CAD.

## Architecture decision

Use `thermalforge-api` as the single browser-facing backend. Port the small,
reusable provider and FOC presentation capabilities into its existing task
pipeline instead of making the frontend aggregate two backends.

```text
Agent UI
  -> /v1 project + task + document APIs
  -> TaskQueue
       -> ARQ + Redis in distributed deployments
       -> managed in-process execution in local development
  -> shared PipelineRunner
       -> document parsing
       -> engineering brief via fixture or OpenAI-compatible provider
       -> clarification loop when required fields are missing
       -> deterministic thermal calculation + governed design selection
       -> curated model artifact association
       -> ready
  -> SSE task events + result/viewer APIs
```

The root `core` backend remains available for its independent engineering tools,
but the Agent does not call it. This avoids duplicate task IDs, databases,
error formats, CORS policies, and lifecycle state.

## Queue and execution

Replace the local no-op queue with a lifecycle-managed in-process queue:

- enqueue returns immediately and never runs the long pipeline inside the HTTP
  request;
- `(task_id, dispatch_token)` identifies one dispatch and deduplicates repeated
  start, retry, or clarification submissions;
- active `asyncio.Task` instances are retained so exceptions are observed;
- application shutdown cancels and awaits active tasks;
- ARQ continues to use deterministic job IDs in distributed mode;
- both queue implementations invoke the same `PipelineRunner`, so local and
  worker behavior cannot drift.

Pipeline stages remain idempotent and re-read current task status before work.
Service-level failures must move the task to `failed`; cancellation must stop
subsequent stages.

## LLM provider

Add an `openai_compatible` implementation of the existing `LLMProvider`
protocol using the already-installed `httpx` dependency.

Configuration:

- `THERMALFORGE_LLM_PROVIDER=openai_compatible`
- `THERMALFORGE_OPENAI_API_KEY` as a `SecretStr`
- `THERMALFORGE_OPENAI_BASE_URL=https://www.micuapi.ai/v1`
- `THERMALFORGE_OPENAI_MODEL=gpt-5.6-sol`

The key stays in `thermalforge-api/.env`, which is ignored by Git. Tests,
responses, logs, and committed examples contain only an empty placeholder.

The provider calls `POST {base_url}/responses`, requests one JSON object that
matches the supplied Pydantic JSON Schema, extracts text from either
`output_text` or Responses API content blocks, and validates it with the
requested response model. Timeouts, connection failures, HTTP failures, empty
output, invalid JSON, and schema violations map to existing domain errors
without returning upstream credentials or raw sensitive headers.

The deterministic fixture remains the default and is used to prove the whole
flow without network or token consumption. The live-provider run is a separate
acceptance gate.

## Completing the task pipeline

After thermal design:

1. Associate the checked-in whole-arm GLB as a task-owned `raw_model` artifact.
2. Associate the Bang three-mesh GLB as a task-owned `normalized_model`
   artifact with node-name metadata for `root.0`, `root.1`, and `root.2`.
3. Advance the existing concept/multiview/model review states with explicit
   events whose payload identifies the source as a curated reference asset.
4. Transition to `ready` only after both artifact bytes are stored and approved.

This stage does not claim that the uploaded requirements generated new CAD.
The UI and artifact metadata must label the meshes as concept references linked
to the calculated design. Missing or unreadable seed assets fail the task
instead of silently showing the old Wall-E fallback.

## Additive viewer contract

Keep the existing `asset` field for compatibility and add optional model
variants:

- preferred segmented model;
- whole model alternative;
- per-variant label and capabilities;
- node-bound parts and explode vectors for the segmented GLB;
- fidelity notices.

Old manifests still render as a single whole-asset model. The content endpoint
continues to verify task ownership, model kind, and approved quality before
serving immutable bytes.

## Agent interaction

The model remains the page's visual center. The following FOC workbench effects
are adapted into the current design rather than copied as a dashboard:

- whole/segmented model switch;
- auto-rotate, wireframe, explode, reset, and accessible asset-info controls;
- node selection for the three Bang meshes using factual generic labels only;
- real backend stage trace in the existing full-process drawer;
- engineering brief, selected thermal solution, heat path, materials, risks,
  assumptions, and validation items in a design-evidence tab;
- sanitized JSON for the current task's brief, analysis, design, and manifest
  in a backend-output tab.

No permanent sidebar, seven-step navigation, metric-card dashboard, or fake CFD
heatmap is introduced. Existing micro-gradients and `--tf-*` tokens remain the
visual source of truth.

## Upload and progress behavior

- Each file shows pending, uploading, uploaded, or failed state.
- Submit remains cancellable.
- A successfully started task immediately leaves the submission state and shows
  backend stage progress.
- SSE reconnects with `Last-Event-ID`; a bounded no-progress watchdog surfaces
  an actionable error if a task produces no new status or event for the
  configured interval.
- `awaiting_input` presents the backend question without losing uploaded files
  or the task ID. An answer dispatches the same pipeline again.
- `failed` and `cancelled` expose retry; `ready` exposes result inspection and a
  new-design action.

## Verification

Backend:

- regression test reproducing the current no-op queue stall;
- in-process dispatch deduplication, exception observation, and shutdown;
- fixture upload through `ready`, including model artifacts and SSE events;
- clarification answer resumes the same task;
- OpenAI-compatible request, response extraction, schema validation, timeout,
  and redacted upstream error tests using `httpx.MockTransport`;
- viewer variant authorization and backward-compatible manifest tests.

Frontend:

- upload state and no-progress error behavior;
- clarification loop;
- result bundle loading;
- whole/segmented, auto-rotate, wireframe, explode, reset, and keyboard controls;
- evidence/output drawer tabs;
- no secret-like fields rendered;
- responsive and reduced-motion coverage.

Acceptance:

- backend lint, types, and full pytest;
- frontend lint, unit tests, production build, and Playwright;
- fixture flow reaches `ready` from a real uploaded text document;
- live `gpt-5.6-sol` flow reaches either `awaiting_input` or `ready` with the
  configured local secret;
- health, SSE, viewer content, cancellation, and restart behavior are checked
  against the running services.
