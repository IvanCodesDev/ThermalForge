# Full Arm PBR Review and Publish Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use test-driven-development and verification-before-completion task-by-task.

**Goal:** Display the real 29-mesh robot arm with its supplied PBR texture maps, preserve exploded selection, then curate backend documentation and publish only intentional repository files.

**Architecture:** `RobotArmViewer` loads the existing full-arm GLB and binds the supplied diffuse, normal, metallic, roughness, and emissive maps to each real mesh. The UI continues to derive component cards from GLB meshes. Publishing remains backend-first because `/frontend/` is intentionally excluded from the repository except for explicitly tracked model assets.

**Tech Stack:** React, TypeScript, Three.js, Vite, Python/Playwright, FastAPI, pytest, Git/GitHub.

---

### Task 1: Bind the real PBR assets

**Files:**
- Modify: `frontend/src/RobotArmViewer.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `scripts/verify_model_review_ui.py`

1. Verify the current UI does not load 29 component meshes.
2. Load `/models/robot-arm/base.glb`.
3. Bind the existing diffuse, normal, metallic, roughness, and emissive images with GLTF-compatible texture orientation and color spaces.
4. Preserve raycast selection and exploded transforms for every mesh.
5. Build the frontend and run the Playwright verification.
6. Inspect the resulting screenshot for the expected multicolor PBR appearance.

### Task 2: Audit backend documentation

**Files:**
- Modify: `README.md`
- Modify/Create: backend documentation under `docs/agent-system/`

1. Document real-mode startup, environment variables, API boundaries, persistence namespaces, provenance completion, Hyper3D lifecycle, and solver adapter handoff.
2. Remove or clearly label stale demo and development-only guidance.
3. Ensure no secret values appear in documentation.

### Task 3: Curate the Git payload

**Files:**
- Modify: `.gitignore` only where necessary.

1. Inspect tracked, modified, ignored, and untracked files.
2. Exclude caches, databases, generated outputs, credentials, temporary HPC scripts, and local assistant state.
3. Confirm whether large model assets are intentional and identify their sizes.
4. Run backend tests, frontend build, and secret-pattern checks.
5. Commit only reviewed files and push `main` to the configured `origin`.
