# ThermalForge Agent UI Phase 0 Implementation Plan

> **Historical plan; superseded by the current implementation.** The legacy
> seven-step pages and local analysis subtree have been removed. Use
> repository-root `docs/design.md` and the current Agent source as
> the maintained design and behavior references.

**Goal:** Replace the seven-step workspace entry point with a single-screen, center-stage 3D Agent experience that supports mock generation, two-message chat, model explosion, and part explanations.

**Architecture:** Keep the existing thermal analysis and content modules as domain sources. Add an isolated `agent` state machine for the mock workflow and an isolated `model` feature for React Three Fiber rendering. `App.tsx` becomes a thin composition root; legacy pages remain in the repository but are no longer reachable from the application entry point.

**Tech Stack:** React 19, TypeScript 6, Vite 8, Vitest, Testing Library, Three.js, React Three Fiber 9, Drei, IBM Plex self-hosted font packages.

**Delivery policy:** Execute inline in the current workspace. Do not commit or push unless the user explicitly requests it.

---

## File map

Create:

- `src/agent/agentTypes.ts` — workflow, message, file, and part types.
- `src/agent/agentReducer.ts` — pure state transitions and local persistence guards.
- `src/agent/agentReducer.test.ts` — state-machine behavior tests.
- `src/agent/mockPipeline.ts` — deterministic mock stage definitions.
- `src/agent/AgentConversation.tsx` — latest-two message presentation.
- `src/agent/AgentComposer.tsx` — file selection, prompt entry, and submit/cancel controls.
- `src/agent/AgentHistoryDrawer.tsx` — complete conversation and stage history.
- `src/agent/AgentExperience.tsx` — screen composition and mock timer orchestration.
- `src/model/ModelStage.tsx` — Canvas, lighting, controls, and HTML control overlay.
- `src/model/JointAssembly.tsx` — base, thermal interface, detachable shell, and animation.
- `src/model/PartDetailSheet.tsx` — selected shell design explanation.
- `src/styles/agent.css` — single-screen responsive visual system.

Modify:

- `package.json` and `package-lock.json` — 3D and font dependencies.
- `src/App.tsx` — render `AgentExperience`.
- `src/App.test.tsx` — test the new entry experience.
- `src/App.css` — import only the new Agent stylesheet.
- `src/index.css` — reset, typography, color tokens, and accessibility defaults.

Preserve:

- `src/analysis/thermalEngine.ts`
- `src/analysis/types.ts`
- `src/data/content.ts`
- `src/utils/report.ts`
- Legacy page files until the new entry experience is verified.

## Task 1: Install and validate dependencies

- [ ] Install runtime dependencies:

  ```powershell
  npm install three @react-three/fiber @react-three/drei @fontsource-variable/ibm-plex-sans @fontsource/ibm-plex-mono
  ```

- [ ] Install Three.js types:

  ```powershell
  npm install --save-dev @types/three
  ```

- [ ] Confirm `package-lock.json` and `package.json` remain in sync:

  ```powershell
  npm install
  ```

  Expected: exit code 0 and no lockfile mismatch.

## Task 2: Build the Agent state machine with TDD

- [ ] Create `src/agent/agentReducer.test.ts` first with failing tests for:
  - initial idle state and welcome message;
  - start requires a prompt or an accepted file;
  - start appends one user message and one stage message;
  - each tick advances exactly one stage;
  - completion enters `ready`;
  - cancel stops future stage progression;
  - only selectors, not state storage, reduce messages to the latest two;
  - corrupt local storage falls back to the initial state.

- [ ] Run the reducer test and verify the expected missing-module failure:

  ```powershell
  npm test -- src/agent/agentReducer.test.ts
  ```

- [ ] Create `src/agent/agentTypes.ts`, `src/agent/mockPipeline.ts`, and `src/agent/agentReducer.ts`.

- [ ] Use a finite set of stages:

  ```ts
  type AgentStage =
    | 'idle'
    | 'reading'
    | 'briefing'
    | 'thermal'
    | 'multiview'
    | 'modeling'
    | 'ready'
  ```

- [ ] Keep reducer actions explicit:

  ```ts
  type AgentAction =
    | { type: 'SET_PROMPT'; prompt: string }
    | { type: 'SET_FILES'; files: AgentFile[] }
    | { type: 'START' }
    | { type: 'ADVANCE' }
    | { type: 'CANCEL' }
    | { type: 'TOGGLE_HISTORY' }
    | { type: 'TOGGLE_EXPLODED' }
    | { type: 'SELECT_PART'; part: ModelPart | null }
    | { type: 'RESET' }
  ```

- [ ] Re-run the focused reducer test until it passes.

## Task 3: Build the single-screen Agent UI with TDD

- [ ] Replace `src/App.test.tsx` first. Mock `ModelStage` to avoid requiring WebGL in JSDOM and add failing tests for:
  - the page has no workflow navigation;
  - the model stage and design input are visible;
  - submit starts the mock workflow;
  - the main conversation renders only the latest two messages;
  - “查看全部” opens complete history;
  - cancel returns the task to a recoverable state.

- [ ] Run the App test and verify it fails against the legacy seven-step UI:

  ```powershell
  npm test -- src/App.test.tsx
  ```

- [ ] Create the conversation, composer, drawer, and experience components.

- [ ] Keep the screen hierarchy stable:

  ```tsx
  <div className="agent-app">
    <header className="agent-header" />
    <main className="agent-main">
      <ModelStage />
      <AgentConversation />
      <AgentComposer />
      <AgentHistoryDrawer />
      <PartDetailSheet />
    </main>
  </div>
  ```

- [ ] Persist state under a versioned local-storage key and resume a running mock stage safely after refresh.

- [ ] Modify `src/App.tsx` to render only `AgentExperience`.

- [ ] Re-run the focused App tests until they pass.

## Task 4: Build the real 3D stage

- [ ] Create `src/model/JointAssembly.tsx` with three semantic scene nodes:
  - `joint-base`;
  - `thermal-interface`;
  - `thermal-shell`.

- [ ] Model the Phase 0 assembly from Three.js primitives so no binary asset is required.

- [ ] Animate exploded positions with frame-rate-independent damping:

  ```ts
  group.position.y = MathUtils.damp(
    group.position.y,
    exploded ? targetOffset : 0,
    7,
    delta,
  )
  ```

- [ ] Ensure shell clicks select the shell only after explosion; otherwise the click triggers whole-model explosion.

- [ ] Create `src/model/ModelStage.tsx` with:
  - `Canvas`;
  - physically plausible key, fill, and rim lights;
  - `OrbitControls` with pan disabled;
  - contact shadow;
  - visible explode/merge and reset controls;
  - pointer-miss selection clearing;
  - a non-WebGL fallback message.

- [ ] Create `src/model/PartDetailSheet.tsx` and source its recommendation title/features from `SOLUTIONS`, preferring `vein-bridge`.

- [ ] Run:

  ```powershell
  npm run build
  ```

  Expected: TypeScript and Vite complete with exit code 0.

## Task 5: Apply the minimal visual system

- [ ] Replace `src/App.css` imports with `src/styles/agent.css`.

- [ ] Update `src/index.css` with:
  - near-black background;
  - warm-white text;
  - thermal-orange accent;
  - IBM Plex Sans and IBM Plex Mono imports;
  - visible focus states;
  - reduced-motion behavior.

- [ ] Implement in `src/styles/agent.css`:
  - 48–56px minimal header;
  - edge-to-edge 3D stage without card borders;
  - bottom gradient layer with only two messages;
  - compact solid composer;
  - non-modal history drawer;
  - temporary part detail sheet;
  - 375px, 768px, and 1440px responsive layouts.

- [ ] Confirm no legacy shell/dashboard stylesheet is imported by the entry point.

## Task 6: Verify Phase 0

- [ ] Run all tests:

  ```powershell
  npm test
  ```

- [ ] Run lint:

  ```powershell
  npm run lint
  ```

- [ ] Run the production build:

  ```powershell
  npm run build
  ```

- [ ] Check IDE diagnostics for every new or modified TypeScript file.

- [ ] Review the implementation against the spec:
  - no top workflow navigation;
  - no permanent sidebars;
  - central 3D remains the largest element;
  - only the latest two messages are visible by default;
  - model explosion and shell explanation work;
  - mock workflow can be cancelled and resumed;
  - existing thermal domain modules remain intact.

- [ ] Report any browser-only visual checks that were not executable as `NOT RUN`, with an explicit manual checklist.
