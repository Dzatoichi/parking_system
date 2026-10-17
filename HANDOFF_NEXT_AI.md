# Handoff for the next AI session

## Project goal and terminology

This repository implements vehicle tracking and cross-camera re-identification for a parking system with nine cameras. Keep these concepts separate:

- **Local track**: a BoT-SORT ID scoped to one camera. The same numeric ID on another camera is unrelated unless evidence links the observations.
- **Gallery**: a set of Re-ID embeddings for a local track or registered journey.
- **Journey/session**: the logical vehicle registration and route across cameras.

Read `ARCHITECTURE_RULES.md` before changing the flow. `TOPOLOGY.md` describes transition detection; `TRACKING.md` is primarily the intended architecture, not proof that every idea there is implemented. `README_FEATURE_CAPTURE_RUN.md` describes the separate lightweight capture runner.

## Branch and integration status

- Integration target: `reid_and_tracking`.
- The feature work for this integration was developed on `feature-candidate-search-v1`.
- Branch heads, open PRs, and ahead/behind counts change. Query GitHub before making a merge decision; do not rely on hard-coded counts from this document or create a `main` branch as an assumption.

## Runtime entry points

### Integrated nine-camera controller

Run from the repository root:

```bash
python run_main_controller.py
```

`run_main_controller.py` coordinates registration, scan-gallery capture, OCR, topology transition tracking, RuntimeReID handoffs, session bindings, and run reporting.

- Camera 1 triggers registration and is the only OCR camera.
- Scan-gallery capture is limited to cameras 1–3.
- Camera 1 → camera 2 scan association is FIFO constrained by LEFT/RIGHT lane and camera-2 zone-entry order.
- Camera 3 topology handoff currently uses FIFO.
- Other supported downstream transitions use topology-gated RuntimeReID candidate matching.
- The general RuntimeReID pipeline uses cameras 2–9. On cameras 2/3, only exact `(camera_id, track_id)` keys owned by active scan sessions are excluded; do not disable all Re-ID tracks on a camera just because scan capture is active.
- A negative journey ID is provisional for an unrecognized plate. It maintains routing without claiming the plate is known.

**Database caution:** `Config.DB_ENABLED` defaults to true. Unless `PARKING_DB_ENABLED=false` is set, the integrated controller attempts to connect to PostgreSQL and can perform real database writes. Do not describe this entry point as a mock-DB-only runner.

### Lightweight/legacy capture runner

`python run_feature_capture.py` is a separate capture/debug path described by `README_FEATURE_CAPTURE_RUN.md`. Its mock output and limitations must not be generalized to `run_main_controller.py`.

### Zone debugger

`run_feature_zone_debug.py` is a read-only visualizer for rectangular zones in `feature_zones.yaml`. The zones use opposite corners `p1` and `p2`; the debugger does not draw, save, or clear zone geometry. Keys: `1` / `2` select LEFT / RIGHT on cameras 1/2, `D` selects DEFAULT on camera 3, Space pauses, and Q/Esc exits. Edit YAML manually to change rectangles.

## Re-ID matching rules

- A transition line produces a movement/topology signal. It is not, by itself, confirmation that a target track belongs to the source journey.
- Candidate tracks must arrive through the configured directed topology and satisfy the handoff time constraints. Do not compare every visible track to every journey and do not fall back to arbitrary FIFO on a Re-ID-scored handoff.
- The current target-camera frame must produce a valid embedding and the searched journey must have a usable identity gallery. The current-frame embedding is compared immediately; near-duplicate filtering controls storage only and does not require multiple stored target samples before comparison.
- On each processed target-camera frame, compare that frame's embedding against every embedding in each journey gallery belonging to an active search task for that destination camera. The displayed/decision score is the maximum pairwise cosine similarity; top-k/mean aggregation is not used. Near-duplicate filtering at 0.92 controls what is stored in the target track history, not whether the current-frame embedding is compared.
- `Config.REID_SIMILARITY_THRESHOLD` is the decision threshold (default 0.65). A topology-eligible candidate is assigned to the highest-scoring active search task once its current-frame best similarity reaches this threshold; the former score-margin requirement is not part of this decision. Keep the identity threshold independent from the near-duplicate storage threshold (default 0.92).
- Overlay label `BEST SIM` is the current frame's maximum cosine similarity against the active search-task galleries for that camera, with the matching journey's plate label. The actual assignment still requires a topology-arrived candidate and a matching pending search task. The score is refreshed per processed frame; do not compare against unrelated journeys outside the target camera's active search tasks.
- Do not loosen thresholds or bypass topology constraints just to make a box green. Green indicates an assigned journey binding, not merely a high diagnostic score.

## Zone and topology details

- `feature_zones.yaml` contains rectangles at 1280×720.
- FeatureZoneManager collects scan galleries on cameras 1–3: camera 1 uses the bottom-center bbox anchor, camera 2 the right-edge center, and camera 3 the top-center.
- `topology.yaml` lines are finite segments. The crossing detector requires meaningful movement and direction/motion alignment; a bbox merely touching a line is not enough. See `TOPOLOGY.md` for details.
- Camera-specific sources are set by `PARKING_CAMERA_1_VIDEO` through `PARKING_CAMERA_9_VIDEO` or `Config.CAMERA_VIDEO_PATHS`. Keep each camera's environment variable separate.
- Scan-gallery capture and general RuntimeReID are separate subsystems. Read `ARCHITECTURE_RULES.md` before changing ownership, sampling, handoff status, or database responsibilities.

## Important deferred issue — do not change in this task

The source-camera handoff lifecycle still has a known issue: on a source EXIT, the source `journey_by_track` binding can be removed before the target camera confirms the handoff. The architecture says that an EXIT line is only a search signal and the old association must remain valid until confirmation. **This issue was explicitly deferred and was not changed by the current fixes.** Do not partially alter source binding/session completion while handling unrelated score, documentation, or camera-source fixes; address it in a separate change with its own tests.

## Verification

The lightweight CI checks should compile the changed runtime modules and execute the test suite in `tests/`. They do not exercise actual video streams, OSNet/OCR weights, camera synchronization, or a live PostgreSQL instance.

Before treating runtime behavior as fully verified, test using the intended video files and model weights. In particular, confirm the lane-constrained 1→2 scan FIFO, camera-3 FIFO handoff, current-frame Re-ID threshold behavior on other transitions, and database settings. Unit tests cannot replace a real-video integration run.

## Constraints to preserve

- Scan-gallery capture remains limited to cameras 1–3; general RuntimeReID remains a separate cameras 2–9 process.
- Exclude only the exact active scan-owned track keys on cameras 2/3.
- Never treat a local `track_id` as a global journey ID.
- Never treat BEST SIM alone as a confirmed match: assignment also requires a topology-arrived candidate and an active search task for that target camera.
- Do not weaken topology or identity-threshold requirements to force matches.
- OCR failure or latency must not stop visual feature capture.
- Do not describe real controller DB writes as mocked, and do not claim a full video/model-runtime test ran unless it actually did.
