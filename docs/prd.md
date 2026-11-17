# Product Requirements Document (PRD) — VehiGuard

| Field | Value |
|---|---|
| Document | `prd.md` |
| Version | 2.0 (Draft for review) |
| Date | 09 Nov 2026 |
| Author | [Vinisha Marina Dsouza] |
| Status | Baseline for development |
| Related documents | [problem_statement.md](problem_statement.md) · [tech_stack.md](tech_stack.md) · [architecture.md](architecture.md) · [phase_definition.md](phase_definition.md) |

**Priority key (MoSCoW):** **M** = Must (needed for the demo) · **S** = Should (important, include if time permits) · **C** = Could (stretch goal)

---

## 1. Purpose and Scope

### 1.1 Purpose
This document defines **what** VehiGuard must do (functional requirements) and **how well** it must do it (non-functional requirements). It is the contract between the problem in [problem_statement.md](problem_statement.md) and the design in [architecture.md](architecture.md).

### 1.2 Product summary
VehiGuard reads vehicle number plates from phone-camera feeds at several camera locations, matches them against stolen and missing vehicle records, records every accepted plate as a **sighting**, and compares sightings across locations to identify **suspected cloned plates** (physically impossible journeys and appearance differences). It collects location- and time-stamped evidence, alerts authorised police personnel, and tracks each case until recovery.

### 1.3 In scope / out of scope
See [problem_statement.md §7](problem_statement.md). Key point: the prototype uses phone cameras and an **own, manually created dummy database** only. It performs **no face recognition**.

## 2. Users and Roles

| Role | Description | Main interactions |
|---|---|---|
| **Camera Operator** | Person setting up and running the phone cameras | Register cameras, start/stop streams, check camera health |
| **Police Officer** | Authorised officer or control-room user | Review alerts, view evidence, update alert and recovery status, create stolen/missing reports |
| **Administrator** | Manages the system | Manage records, users, cameras, thresholds, retention |
| **Viewer** | Examiner or guide (read-only) | View dashboard, logs and metrics |

## 3. Goals and Success Metrics

The targets below are **proposed** and must be confirmed (or honestly revised) after Phase 8 evaluation on the project's own test set.

| ID | Metric | Target |
|---|---|---|
| M1 | Plate detection recall (daylight, test set ≥ 100 images) | ≥ 90% |
| M2 | Plate OCR exact-match accuracy (after voting and validation) | ≥ 85% |
| M3 | Vehicle type accuracy / colour-family accuracy (test set ≥ 100 vehicle crops) | ≥ 90% / ≥ 80% |
| M4 | Clone-detection correctness on the scripted clone and non-clone scenarios (S02, S05, S06, S17) | 100% |
| M5 | Genuine multi-camera sightings wrongly flagged as suspected clones (scripted set) | 0 (count reported) |
| M6 | Decision-matrix correctness on scripted scenarios (§9) | 100% |
| M7 | Alerts lost due to delivery failure (outbox + retry) | 0 |
| M8 | Accepted plate → decision and alert record created | ≤ 2 s |

## 4. Functional Requirements (FR)

### 4.1 Capture (FR-CAP)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-CAP-01 | Ingest a live video stream from a phone camera over the local network (or USB) and extract frames at a configurable rate | M | Stream opens; ≥ 5 fps processed from one camera on the dev laptop |
| FR-CAP-02 | Support alternative inputs (laptop webcam, video file, image folder) for testing and reproducible demos (replay mode) | S | Same pipeline runs from each source with a config switch |
| FR-CAP-03 | Run two or more cameras at the same time, each bound to its own camera ID | M | Two cameras processed together at ≥ 3 fps each |
| FR-CAP-04 | Maintain a camera registry (ID, name, latitude, longitude, nearest station, source). Every frame is timestamped with the **server clock** when received | M | Each sighting shows camera ID and server timestamp |
| FR-CAP-05 | Operator console shows a live preview with overlays (vehicle box, plate box, plate text) | S | Overlays render at ≥ 5 fps |
| FR-CAP-06 | Auto-reconnect when a stream drops | M | Resumes within 10 s without restart |
| FR-CAP-07 | Show camera health: online/offline and time of last frame | S | Status visible on dashboard |

### 4.2 Vehicle and Plate Recognition (FR-PLT)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-PLT-01 | Detect vehicles (car, motorcycle, bus, truck) in each frame using YOLO | M | Vehicle box and class returned with confidence |
| FR-PLT-02 | Localise the number plate and crop it with a small margin | M | Plate crop saved as evidence |
| FR-PLT-03 | Preprocess the crop: grayscale, denoise, contrast enhancement, perspective/skew correction | M | Preprocessing improves OCR accuracy on the tilted/blurred subset (measured in Phase 2) |
| FR-PLT-04 | Run OCR and return text with a confidence score | M | PaddleOCR primary, EasyOCR fallback |
| FR-PLT-05 | Normalise text (uppercase, strip spaces/hyphens), fix position-based confusions (e.g. O↔0, I↔1, B↔8, S↔5), and validate against configurable Indian plate patterns (standard, BH series) | M | Invalid strings are rejected, not guessed |
| FR-PLT-06 | Multi-frame voting: accept a plate only when the same text wins a majority over the last N frames (default N = 10) and mean confidence passes the gate | M | Single-frame misreads never reach the registry lookup or the clone analysis |
| FR-PLT-07 | If no valid plate is accepted within a timeout (default 10 s), outcome = `NO_PLATE`: log it, save evidence, **raise no alert** | M | No alert is created for `NO_PLATE` |
| FR-PLT-08 | If an accepted plate is not an exact match but is within edit distance 1 of an active stolen/missing plate, create a `POSSIBLE_MATCH` review item. It is **never** an automatic alert and never feeds clone analysis | S | Item appears in the officer's review list with reduced confidence |
| FR-PLT-09 | Save the best vehicle frame and plate crop for each sighting | M | Linked to the sighting |

### 4.3 Registry and Stolen/Missing Matching (FR-REG)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-REG-01 | Look up the accepted plate in the vehicle registry | M | Returns the record or "not found" |
| FR-REG-02 | The registry stores plate, vehicle type, make, model, colour and a fictional owner name | M | Fields present in dummy data |
| FR-REG-03 | Maintain stolen/missing reports (report type, fictional FIR reference, reported time and place, recovery status). Match accepted plates against reports whose status is not `RECOVERED` or `CLOSED` | M | Matching report found for every stolen/missing test plate |
| FR-REG-04 | A stolen or missing match raises a **HIGH** alert within 2 s of the decision, subject to the OCR confidence gate | M | Alert created and routed |
| FR-REG-05 | A plate that is not in the registry is logged as `UNKNOWN_PLATE` (INFO), still stored as a sighting and still used for clone analysis. It raises an alert only if the config switch `FLAG_UNREGISTERED` is on (open decision D-01) | M | Unknown plate creates a sighting and no alert by default |

### 4.4 Sightings (FR-SIG)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-SIG-01 | Every accepted plate creates a sighting: camera, plate, OCR confidence, server timestamp, vehicle type, colour family, best frame and plate crop | M | One row per sighting with all fields |
| FR-SIG-02 | De-duplicate: the same plate at the same camera within `SIGHTING_COOLDOWN_S` (default 30 s) updates one sighting and keeps the best-quality frame | M | A vehicle waiting in view creates one sighting |
| FR-SIG-03 | Provide a per-plate sighting timeline across all cameras | S | Timeline shows camera, time and thumbnail |

### 4.5 Clone Detection (FR-CLN)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-CLN-01 | For each new sighting, compare it with the same plate's earlier sightings at **other** cameras within `CLONE_WINDOW_H` (default 24 h) | M | Same-camera sightings are never compared |
| FR-CLN-02 | **Impossible-journey rule:** with *d* = Haversine distance between the two camera coordinates and *Δt* = time gap, flag when `d ≥ MIN_CLONE_DISTANCE_KM` and `d > MAX_PLAUSIBLE_SPEED_KMH × (Δt + TIME_TOLERANCE_S)`. Straight-line distance never exceeds road distance, so the rule is conservative | M | Verified with scripted cases, including borderline values |
| FR-CLN-03 | Store the journey: from/to camera, distance, time gap and required speed | M | Visible on the alert detail |
| FR-CLN-04 | Combine the three signals (impossible journey, appearance mismatch between sightings, appearance mismatch with the registry) to set alert type and severity according to §5 | M | Each matrix row covered by a test |
| FR-CLN-05 | Attach both sightings' evidence side by side to the alert | M | Alert detail shows both images, cameras and times |
| FR-CLN-06 | Alert wording says **"suspected"** clone. Only an officer can mark a case `CLOSED_CONFIRMED` | M | No automatic "confirmed" state |
| FR-CLN-07 | Only sightings whose plate passed the OCR gate are compared | M | Low-confidence reads never create a clone alert |

### 4.6 Vehicle Appearance (FR-APP)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-APP-01 | Determine vehicle type (car, motorcycle, bus, truck) from the detector class, by majority over the voting frames | M | Type stored on the sighting |
| FR-APP-02 | Determine the dominant body colour and map it to a **colour family** (white/silver/grey, black, red, blue, green, yellow/orange, brown, other), by majority over the voting frames | M | Colour family stored on the sighting |
| FR-APP-03 | **Registry check (RM):** compare the observed type and colour family with the registry record | M | Mismatch recorded with reason code |
| FR-APP-04 | **Sighting check (AM):** compare the observed type and colour family with the plate's earlier sighting | M | Mismatch recorded with reason code |
| FR-APP-05 | If colour or type cannot be determined (poor light, occlusion), the value is `UNKNOWN`. `UNKNOWN` is **never** treated as a mismatch | M | Verified by unit tests |
| FR-APP-06 | Optional additional signal: similarity of a pretrained image-feature embedding of the vehicle crop | C | Score stored; not used for alerts unless enabled |

### 4.7 Evidence (FR-EVD)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-EVD-01 | Save the best vehicle frame and the plate crop for each sighting | M | Files linked to the sighting |
| FR-EVD-02 | Evidence records the camera ID, coordinates and server timestamp | M | Shown with the image on the dashboard |
| FR-EVD-03 | Retention: purge evidence older than `EVIDENCE_RETENTION_DAYS` (default 30), **except** evidence linked to an open alert or case | M | Verified with back-dated test data |
| FR-EVD-04 | Store a SHA-256 hash of each evidence file when saved, to show it was not altered | S | Hash shown on detail view |

### 4.8 Alerts and Notifications (FR-ALR)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-ALR-01 | Alert payload contains alert ID, type, severity, plate, camera, coordinates, timestamp, reason codes, scores and evidence images | M | Schema validated |
| FR-ALR-02 | Alert types: `STOLEN_VEHICLE`, `MISSING_VEHICLE`, `SUSPECTED_CLONE`, `APPEARANCE_MISMATCH`, `UNREGISTERED_VEHICLE` (only when `FLAG_UNREGISTERED` is on) | M | Each type produced by a test scenario |
| FR-ALR-03 | Deliver to the nearest station by dashboard plus email (SMTP). HIGH and MEDIUM alerts are emailed; LOW alerts are dashboard-only | M | Email received or logged in simulated mode |
| FR-ALR-04 | Reliable delivery using an outbox with retry and exponential back-off | M | No loss after a simulated network outage |
| FR-ALR-05 | De-duplicate: the same plate and alert type within a cooldown (default 15 min) merges into one alert and increments a counter | S | Second detection increments the counter |
| FR-ALR-06 | **Simulated mode** sends alerts to a mock station inbox; real channels are enabled by config | M | Demo works with no external services |
| FR-ALR-07 | Alert status workflow: `NEW → ACKNOWLEDGED → UNDER_INVESTIGATION → CLOSED_CONFIRMED` or `CLOSED_FALSE_ALARM`. Each change records user, time and note | M | Status visible on dashboard; history stored |

### 4.9 Case and Recovery Tracking (FR-CASE)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-CASE-01 | Each stolen/missing report has a recovery status: `REPORTED`, `DETECTED`, `UNDER_INVESTIGATION`, `RECOVERED`, `CLOSED` | M | Status stored on the report |
| FR-CASE-02 | When a stolen/missing alert is created and the report is `REPORTED`, the status moves automatically to `DETECTED` | M | Verified by scenario S03 |
| FR-CASE-03 | Officers move the status along the allowed transitions in [architecture.md §6.3](architecture.md); each change records user, time, optional location and a note | M | Disallowed transitions are rejected |
| FR-CASE-04 | Officers can create a stolen/missing report for a vehicle in the registry | M | Report appears in matching immediately |
| FR-CASE-05 | Dashboard shows the number of reports in each recovery status and the time from report to detection | S | Chart renders from real data |

### 4.10 Geo-location and Routing (FR-GEO)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-GEO-01 | Maintain camera and police-station tables with coordinates | M | Present in the seed data |
| FR-GEO-02 | Select the nearest station for a camera by Haversine distance | M | Correct station for all test cameras |
| FR-GEO-03 | Map view with camera markers, alert markers and the journey line between the two sightings of a suspected clone | S | Map renders from real data |
| FR-GEO-04 | Optionally use the phone's GPS instead of fixed camera coordinates | C | Falls back to the registered coordinates if unavailable |

### 4.11 Dashboard (FR-DSH)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-DSH-01 | Login with role-based access | M | Unauthorised pages and actions blocked |
| FR-DSH-02 | Live monitor: recent sightings with outcome badges and camera status | M | Updates within 5 s |
| FR-DSH-03 | Alerts page with filters (type, severity, status, date, station) | M | Filters return correct rows |
| FR-DSH-04 | Alert detail: reason codes, scores, evidence side by side, journey map and status controls | M | All fields on one screen |
| FR-DSH-05 | Search by plate and date; per-plate sighting timeline | M | Timeline shows all cameras |
| FR-DSH-06 | Stolen/missing reports page with recovery status controls | M | Status change end-to-end works |
| FR-DSH-07 | Analytics: sightings and alerts per day, hourly pattern, top flagged plates, alert map, recovery pipeline | S | Charts render from real data |
| FR-DSH-08 | Export logs and reports to CSV | S | File downloads correctly |
| FR-DSH-09 | Review list for `POSSIBLE_MATCH` items | S | Officer can dismiss or promote to an alert |

### 4.12 Administration and Data (FR-ADM)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-ADM-01 | Manage vehicles, stolen/missing reports, stations, cameras and users via the admin UI or scripts | M | CRUD operations succeed |
| FR-ADM-02 | Reproducible seed script that builds the full dummy database | M | One command rebuilds the dataset |
| FR-ADM-03 | Configuration file or panel for thresholds, timeouts, cooldowns and switches | S | Changes apply without code edits |
| FR-ADM-04 | Retention job implements FR-EVD-03 | M | Verified with back-dated test data |

### 4.13 Logging, Audit and Evaluation (FR-LOG)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-LOG-01 | Log every sighting and decision: plate, scores, signals, outcome, reason codes, timings | M | Row per sighting |
| FR-LOG-02 | Append-only audit log for officer, operator and admin actions (optionally hash-chained) | M | No update/delete path |
| FR-LOG-03 | Evaluation script outputs plate, appearance, clone-detection and latency tables | M | Produces report-ready tables |

### 4.14 Authentication and Authorisation (FR-AUTH)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-AUTH-01 | Roles: Admin, Police Officer, Camera Operator, Viewer | M | Permission matrix enforced |
| FR-AUTH-02 | Passwords stored hashed (bcrypt/argon2); token-based API sessions | M | No plaintext secrets in the database |
| FR-AUTH-03 | Session timeout and logout | S | Idle session expires |

## 5. Decision Matrix (Authoritative Business Rules)

**Signals.** For each accepted plate the engine computes:

- **IJ** — impossible journey against an earlier sighting at another camera (FR-CLN-02)
- **AM** — appearance mismatch between this sighting and the earlier sighting (FR-APP-04)
- **RM** — appearance mismatch between this sighting and the registry record (FR-APP-03)

`UNKNOWN` appearance values never produce AM or RM.

| # | Condition | Outcome | Alert type | Severity | Delivery |
|---|---|---|---|---|---|
| 1 | No valid plate accepted, or confidence below the gate | `NO_PLATE` / `LOW_CONFIDENCE`: log and save evidence | — | — | No alert |
| 2 | Plate matches an active `STOLEN` report | Alert; report → `DETECTED` (if `REPORTED`) | `STOLEN_VEHICLE` | HIGH | Dashboard + email |
| 3 | Plate matches an active `MISSING` report | Alert; report → `DETECTED` (if `REPORTED`) | `MISSING_VEHICLE` | HIGH | Dashboard + email |
| 4 | IJ **and** (AM **or** RM) | Suspected clone | `SUSPECTED_CLONE` | HIGH | Dashboard + email |
| 5 | IJ only | Suspected clone, officer to verify | `SUSPECTED_CLONE` | MEDIUM | Dashboard + email |
| 6 | No IJ, but AM **or** RM | Appearance mismatch, officer to review | `APPEARANCE_MISMATCH` | LOW | Dashboard only |
| 7 | Plate in registry, no report, no signals | **PASS**, logged | — | INFO | — |
| 8 | Plate not in registry, no IJ | `UNKNOWN_PLATE`, logged (alert only if `FLAG_UNREGISTERED`) | — / `UNREGISTERED_VEHICLE` | INFO / MEDIUM | — / Dashboard + email |

**Notes**

- Rows 2 and 3 are evaluated **independently** of rows 4 to 6. One sighting can raise more than one alert (for example a stolen vehicle that also shows IJ). Row 7 applies only when no other row raised an alert.
- A stolen or missing match where the observed appearance differs from the registry (RM) keeps its HIGH alert and adds the reason code `APPEARANCE_MISMATCH`, because the plate may have been copied from a stolen vehicle.
- Row 8 with IJ follows rows 4 or 5, using AM only (there is no registry record to compare).

**Safety rules**

1. `NO_PLATE`, `LOW_CONFIDENCE`, `UNKNOWN` appearance and `POSSIBLE_MATCH` can only lead to *logging or officer review*, never to a pass, never to an automatic HIGH alert, and never into clone analysis.
2. Every alert is a **lead**, not a verdict. Only an officer can set `CLOSED_CONFIRMED`.
3. The decision engine is deterministic: the same inputs and configuration always give the same outcome.

## 6. Non-Functional Requirements (NFR)

### 6.1 Performance

| ID | Requirement | Target |
|---|---|---|
| NFR-PERF-01 | Plate recognition result after the plate is stable in view | ≤ 3 s (GPU), ≤ 6 s (CPU) |
| NFR-PERF-02 | Accepted plate → decision and alert record | ≤ 2 s |
| NFR-PERF-03 | Sustained processing rate on the dev laptop | ≥ 5 fps (one camera); ≥ 3 fps each (two cameras) |
| NFR-PERF-04 | Dashboard page load with ≥ 10,000 sighting rows | ≤ 2 s |
| NFR-PERF-05 | Clone analysis for one sighting (database query + rule) | ≤ 500 ms |

### 6.2 Accuracy and Correctness

| ID | Requirement | Target |
|---|---|---|
| NFR-ACC-01 | Plate detection recall (daylight) | ≥ 90% |
| NFR-ACC-02 | Plate OCR exact-match | ≥ 85% |
| NFR-ACC-03 | Vehicle type accuracy / colour-family accuracy | ≥ 90% / ≥ 80% |
| NFR-ACC-04 | False clone alerts are measured and reported | Reported |
| NFR-ACC-05 | No silent failures: every non-pass state has a reason code | 100% |
| NFR-ACC-06 | Decision engine is deterministic | 100% |

### 6.3 Reliability and Availability

| ID | Requirement |
|---|---|
| NFR-REL-01 | Alert delivery retried at least 5 times with exponential back-off, then flagged `FAILED` on the dashboard |
| NFR-REL-02 | A stream interruption does not crash the pipeline; auto-reconnect within 10 s; other cameras keep running |
| NFR-REL-03 | Database writes for a sighting and its alerts are transactional (no half-written outcomes) |
| NFR-REL-04 | Health-check endpoint reports status of models, database, cameras and notifier |
| NFR-REL-05 | A failing external service (SMTP) must not block detection or decisioning |

### 6.4 Security

| ID | Requirement |
|---|---|
| NFR-SEC-01 | Secrets (SMTP password, JWT secret, database password) kept in environment variables / `.env`, never committed to the repository |
| NFR-SEC-02 | Passwords hashed (bcrypt/argon2); minimum password policy enforced |
| NFR-SEC-03 | Evidence images served only through authenticated endpoints |
| NFR-SEC-04 | Strict input validation on every API endpoint (typed request models) |
| NFR-SEC-05 | Rate limiting on the login endpoint |
| NFR-SEC-06 | HTTPS for anything exposed beyond the local network |
| NFR-SEC-07 | Dependency vulnerability scan (`pip-audit`, `npm audit`) before the final demo |
| NFR-SEC-08 | The React dashboard calls only the VehiGuard API, with CORS limited to the dashboard origin |

### 6.5 Privacy and Compliance

| ID | Requirement |
|---|---|
| NFR-PRV-01 | Only consented volunteer data, own captures, or public-licensed datasets; consent records retained |
| NFR-PRV-02 | Data minimisation: evidence images purged after the retention period (default 30 days), except for open cases |
| NFR-PRV-03 | Purpose limitation: data used only for the functions defined in this PRD |
| NFR-PRV-04 | Right to removal: an admin can delete a volunteer's vehicle records and evidence on request |
| NFR-PRV-05 | No face detection, recognition or storage of faces for matching |
| NFR-PRV-06 | Role-based access limits who can see evidence and reports |
| NFR-PRV-07 | Every alert status change has a recorded human actor |

### 6.6 Usability

| ID | Requirement |
|---|---|
| NFR-USA-01 | A new operator can register a camera and run a session after ≤ 5 minutes of instruction |
| NFR-USA-02 | Severity uses colour-coded badges **plus text**, not colour alone |
| NFR-USA-03 | Alert detail shows the reason in plain language ("Seen 38 km away 6 minutes earlier") |
| NFR-USA-04 | Error messages state what happened and what to do next |

### 6.7 Maintainability and Testability

| ID | Requirement |
|---|---|
| NFR-MNT-01 | Modular code with clear interfaces between capture, vision, decision, notification and storage |
| NFR-MNT-02 | Decision engine and clone analyser have 100% branch coverage against §5; overall unit-test coverage ≥ 70% |
| NFR-MNT-03 | Type hints, linting (ruff) and formatting (black) enforced by pre-commit |
| NFR-MNT-04 | Recorded-session replay mode gives deterministic, repeatable tests |
| NFR-MNT-05 | All thresholds and timeouts are configuration, not hard-coded |

### 6.8 Portability and Compatibility

| ID | Requirement |
|---|---|
| NFR-POR-01 | Runs on Windows 10/11 and Ubuntu 22.04+ with Python 3.10 or 3.11 |
| NFR-POR-02 | Works with any phone camera app that exposes a stream or appears as a webcam device; webcam and video-file fallbacks |
| NFR-POR-03 | Optional Docker setup for repeatable environments |

### 6.9 Observability and Explainability

| ID | Requirement |
|---|---|
| NFR-OBS-01 | Structured logs with a correlation (sighting) ID on every line |
| NFR-OBS-02 | Stage timings recorded per sighting (capture, detect, OCR, appearance, decision) |
| NFR-OBS-03 | Every decision stores reason codes and the values behind them (distance, gap, required speed, colours compared) |

### 6.10 Scalability (Design Headroom)

| ID | Requirement |
|---|---|
| NFR-SCL-01 | The prototype serves two or three cameras, but the data model supports many cameras and stations |
| NFR-SCL-02 | The storage layer is replaceable (PostgreSQL → PostgreSQL with PostGIS) and the geospatial calculation sits behind one function, so it can be swapped without changing business logic |

### 6.11 Ethical Requirements

| ID | Requirement |
|---|---|
| NFR-ETH-01 | OCR and appearance performance is evaluated across varied lighting, angles, dirt and distance, and reported honestly, including failures |
| NFR-ETH-02 | The report states the limitations of cross-location analysis ([problem_statement.md §3.3](problem_statement.md)) |
| NFR-ETH-03 | The system is decision support; a human decides on every alert |

## 7. Data Requirements

| Dataset | Minimum size (prototype) | Source | Notes |
|---|---|---|---|
| Plate images (detector training/validation) | 500–1,000 labelled | Public datasets + own photos | Check dataset licences |
| Plate test set (held out) | ≥ 100 images, varied angle/light/blur | Own captures | Never used for training |
| Vehicles (registry) | ~20–30 records | Manually created | Mixed types and colours; fictional owners; include the test vehicles |
| Stolen / missing reports | 4–6 | Manually created | Fictional FIR references; mix of `STOLEN` and `MISSING`; different recovery statuses |
| Volunteer vehicles with photos/video | 6–10 vehicles | Consenting volunteers or own captures | Includes real plates; consent form in [consent_form.md](consent_form.md) |
| Appearance test set | ≥ 100 vehicle crops with type and colour labels | Own captures + public images | Labelled by hand |
| Police stations / cameras | 3 / 3 | Manually created | Camera coordinates are assigned (simulated) |
| Scenario recordings | One clip or image set per scenario S01–S17 | Own captures | For replay mode |

## 8. Assumptions, Dependencies and Constraints

- Phones and laptop are on the same Wi-Fi network (or connected by USB) during the demo.
- Camera coordinates are **assigned** because the phones are physically close; the report states this clearly (assumption A2).
- Timestamps come from the laptop clock when frames are received (assumption A3).
- If only one phone can stream at a time, a second location is represented by re-registering the phone or by recorded video (assumption A5).
- Free-tier services only (PostgreSQL, SMTP, map tiles).
- All external dependencies (models, libraries, database) are installed and tested **before** Phase 2 to avoid late environment issues.

## 9. Acceptance Scenarios

Each scenario must be demonstrated and its result recorded in the evaluation report.

| ID | Scenario | Expected result |
|---|---|---|
| S01 | Registered vehicle, matches its registry description, seen at one camera | PASS, logged |
| S02 | Same registered vehicle seen at Camera A and then Camera B with a plausible journey | PASS; no clone alert |
| S03 | Plate matches a `STOLEN` report | HIGH `STOLEN_VEHICLE` alert; report → `DETECTED` |
| S04 | Plate matches a `MISSING` report | HIGH `MISSING_VEHICLE` alert; report → `DETECTED` |
| S05 | Same plate at A and B with an impossible journey, and a different-looking vehicle | HIGH `SUSPECTED_CLONE` with both evidence sets |
| S06 | Same plate at A and B with an impossible journey, and a similar-looking vehicle | MEDIUM `SUSPECTED_CLONE` |
| S07 | Plate registered to a white car but seen on a red motorcycle (one camera) | LOW `APPEARANCE_MISMATCH` |
| S08 | Plate not in the registry, seen once | `UNKNOWN_PLATE` logged; no alert |
| S09 | No plate visible | `NO_PLATE` logged; no alert |
| S10 | OCR read is one character away from a stolen plate | `POSSIBLE_MATCH` review item; no alert |
| S11 | Low light makes colour unreadable | Colour `UNKNOWN`; no appearance alert |
| S12 | Same flagged vehicle seen twice within the cooldown | Single merged alert |
| S13 | Network or email down during an alert, restored later | Alert delivered after retry |
| S14 | Officer moves a stolen report `DETECTED → UNDER_INVESTIGATION → RECOVERED` with notes | Statuses and audit entries recorded |
| S15 | A camera stream drops and returns | Reconnects within 10 s; other camera unaffected |
| S16 | A Viewer tries to change a recovery status | Request rejected |
| S17 | The same plate repeatedly seen at the same camera | One sighting; no clone check against itself |

## 10. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | OCR accuracy low on Indian plates (fonts, dirt, tilt) | Medium | High | Fine-tune detector; position-aware correction; multi-frame voting; format validation | Dev |
| R2 | Colour detection unreliable in changing light | High | Medium | Colour families; majority vote; `UNKNOWN` state; appearance alone is only LOW severity | Dev |
| R3 | False clone alert from a misread plate | Medium | High | Confidence gate; voting; fuzzy matches go to review only; IJ-only alerts are MEDIUM and need officer verification | Dev |
| R4 | PaddlePaddle/PyTorch dependency conflicts | Medium | Medium | Isolated virtual environment; install and test early; EasyOCR fallback | Dev |
| R5 | Phone streaming latency or drops; only one phone can stream | Medium | Medium | USB or Wi-Fi alternatives; auto-reconnect; recorded-session replay | Dev |
| R6 | Demo cannot show a real long-distance journey | High | Medium | Assigned camera coordinates, scripted recordings, documented clearly | Dev |
| R7 | External service limits (SMTP) | High | Low | Simulated mode as default | Dev |
| R8 | Scope creep | Medium | High | MoSCoW priorities; MVP cut line in [phase_definition.md](phase_definition.md) | Dev |
| R9 | Privacy or ethics concerns raised by examiners | Medium | Medium | Consent forms, dummy data, no face recognition, human in the loop, limitations section | Dev |
| R10 | Demo-day failure | Medium | High | Recorded replay mode; backup video; pre-demo checklist | Dev |
| R11 | Learning load of a new stack (PaddleOCR, PostgreSQL, React) | Medium | Medium | Early spikes in Phase 0; EasyOCR fallback; keep the UI small first | Dev |

## 11. Out of Scope / Future Work

- Integration with real databases (Vahan, CCTNS) under official authorisation
- Live CCTV and traffic-camera networks
- Make and model recognition; learned visual re-identification of vehicles
- Tracking a flagged vehicle's route across junctions
- Night-vision / IR support
- Mobile app for officers
- Blockchain-based tamper-proof logging (hash-chained audit log is the prototype step)
- Edge AI deployment
- Face recognition (deliberately excluded)

## 12. Open Decisions

| ID | Question | Current default | Needs decision from |
|---|---|---|---|
| D-01 | Should plates not found in the registry raise an alert? | No: log only. The dummy registry is small, and a real registry is out of scope. Switch `FLAG_UNREGISTERED` available | Project owner / guide |
| D-02 | What is the maximum plausible speed for the impossible-journey rule? | 120 km/h | Project owner / guide |
| D-03 | Should an impossible journey with similar-looking vehicles (IJ only) be MEDIUM or HIGH? | MEDIUM, because a misread plate can cause it | Project owner / guide |

## 13. Traceability

Requirement groups map to modules in [architecture.md](architecture.md) and to delivery phases in [phase_definition.md §16](phase_definition.md).

## 14. Revision History

| Version | Date | Change |
|---|---|---|
| 1.0 | 04 Oct 2026 | First draft for the earlier VehiLence idea (plate detection with face verification) |
| 2.0 | 09 Nov 2026 | Project changed to VehiGuard: stolen and cloned vehicle detection network. Face verification, watchlists and owner confirmation removed. Added sightings, cross-camera clone detection, appearance comparison, evidence collection and recovery tracking. Stack changed to PaddleOCR, PostgreSQL and React. Own dummy database and phone cameras retained |
