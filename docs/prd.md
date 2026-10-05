# Product Requirements Document (PRD) — VehiLence

| Field | Value |
|---|---|
| Document | `prd.md` |
| Version | 1.0 (Draft for review) |
| Date | 04 Oct 2026 |
| Author | [Vinisha Marina Dsouza] |
| Status | Baseline for development |
| Related documents | [problem_statement.md](problem_statement.md) · [tech_stack.md](tech_stack.md) · [architecture.md](architecture.md) · [phase_definition.md](phase_definition.md) |

**Priority key (MoSCoW):** **M** = Must (needed for the demo) · **S** = Should (important, include if time permits) · **C** = Could (stretch goal)

---

## 1. Purpose and Scope

### 1.1 Purpose
This document defines **what** VehiLence must do (functional requirements) and **how well** it must do it (non-functional requirements). It is the contract between the problem in [problem_statement.md](problem_statement.md) and the design in [architecture.md](architecture.md).

### 1.2 Product summary
VehiLence reads a vehicle's number plate from a phone-camera feed, checks it against a registry, verifies that the driver's face matches the registered owner, screens unmatched drivers against missing-person and wanted records (with human confirmation), lets the owner approve or complain, and sends verified alerts to the nearest police station.

### 1.3 In scope / out of scope
See [problem_statement.md §7](problem_statement.md). Key point: the prototype uses a phone camera and **manually created dummy databases** only.

## 2. Users and Roles

| Role | Description | Main interactions |
|---|---|---|
| **Checkpoint Operator** | Person running the capture at the checkpoint | Start/stop session, trigger face capture, see outcome |
| **Police Operator** | Control-room user supervising alerts | Review queue: confirm / reject; acknowledge alerts |
| **Vehicle Owner** | Registered owner of a vehicle | Receives Allow / Complain notification |
| **Administrator** | Manages the system | Manage records, users, thresholds, retention |
| **Evaluator / Viewer** | Examiner or guide (read-only) | View dashboard, logs, metrics |

## 3. Goals and Success Metrics

The targets below are **proposed** and must be confirmed (or honestly revised) after Phase 8 evaluation on the project's own test set.

| ID | Metric | Target |
|---|---|---|
| M1 | Plate detection recall (daylight, test set ≥ 100 images) | ≥ 90% |
| M2 | Plate OCR exact-match accuracy (after voting and validation) | ≥ 85% |
| M3 | Face verification: True Accept Rate at False Accept Rate ≤ 1% (volunteer set) | ≥ 90% |
| M4 | End-to-end decision time (plate + face → outcome, excluding human/owner wait) | ≤ 10 s |
| M5 | Decision-matrix correctness on scripted scenarios (§9) | 100% |
| M6 | Watchlist alerts dispatched without a recorded human decision | 0 |
| M7 | Alerts lost due to network failure (outbox + retry) | 0 |

## 4. Functional Requirements (FR)

### 4.1 Capture (FR-CAP)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-CAP-01 | Ingest a live video stream from an Android phone camera over the local network and extract frames at a configurable rate | M | Stream opens from a URL; ≥ 5 fps processed on the dev laptop |
| FR-CAP-02 | Support alternative inputs (laptop webcam, video file, image folder) for testing and reproducible demos | S | Same pipeline runs from each source with a config switch |
| FR-CAP-03 | Two-stage capture per session: **Stage A** plate, **Stage B** driver face (auto-triggered when a usable face is present, or by operator button) | M | Both stages complete and are linked to one session ID |
| FR-CAP-04 | Every session has a unique ID, start/end time and checkpoint ID | M | Visible in logs and dashboard |
| FR-CAP-05 | Operator console shows live preview with overlays (vehicle box, plate box, plate text, face box) | S | Overlays render at ≥ 5 fps |
| FR-CAP-06 | Auto-reconnect when the stream drops | M | Resumes within 10 s without restart |

### 4.2 Vehicle and Plate Recognition (FR-PLT)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-PLT-01 | Detect vehicles (car, motorcycle, bus, truck) in each frame using YOLOv8 | M | Vehicle box returned with confidence |
| FR-PLT-02 | Localise the number plate and crop it with a small margin | M | Plate crop saved as evidence |
| FR-PLT-03 | Preprocess the crop: grayscale, denoise, contrast enhancement, perspective/skew correction | M | Preprocessing improves OCR accuracy on the tilted/blurred subset (measured in Phase 2) |
| FR-PLT-04 | Run OCR and return text with a confidence score | M | EasyOCR primary, Tesseract fallback |
| FR-PLT-05 | Normalise text (uppercase, strip spaces/hyphens), fix position-based confusions (e.g. O↔0, I↔1, B↔8, S↔5), and validate against configurable Indian plate patterns (standard, BH series, temporary) | M | Invalid strings are rejected, not guessed |
| FR-PLT-06 | Multi-frame voting: accept a plate only when the same text wins a majority over the last N frames (default N = 10) | M | Single-frame misreads do not reach the registry lookup |
| FR-PLT-07 | If exact lookup fails, allow a fuzzy lookup (edit distance ≤ 1) **only for operator review**, never for automatic police alerts | S | Fuzzy hits appear in the review queue with reduced confidence |
| FR-PLT-08 | If no valid plate is accepted within a timeout (default 10 s), outcome = `NO_PLATE` and the case goes to operator review | M | No automatic police alert is created |
| FR-PLT-09 | Save the best vehicle frame and plate crop as evidence | S | Linked to the session |

### 4.3 Registry Verification (FR-REG)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-REG-01 | Look up the accepted plate in the vehicle registry | M | Returns record or "not found" |
| FR-REG-02 | Classify as `REGISTERED_VALID`, `TEMP_VALID`, `TEMP_EXPIRED`, `UNREGISTERED`, `STOLEN`, `MISSING`, `BLACKLISTED` | M | One status per lookup, stored with the session |
| FR-REG-03 | Support registration types **Permanent**, **Temporary** (with `valid_until`) and **Trade/Dealer** | M | A new car on a valid temporary registration is **not** flagged |
| FR-REG-04 | `UNREGISTERED`, `STOLEN`, `MISSING`, `BLACKLISTED` → **HIGH** police alert, subject to the OCR confidence gate (FR-PLT-06/FR-HC-05) | M | Alert created within 2 s of the decision |
| FR-REG-05 | `TEMP_EXPIRED` → **MEDIUM** dashboard alert and continue to face verification | S | Alert visible; flow continues |
| FR-REG-06 | Store optional vehicle attributes (make, model, colour) for future clone detection | C | Fields present in schema |

### 4.4 Face Verification (FR-FACE)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-FACE-01 | Detect faces in the driver capture and select the driver (largest/most central face) | M | One face selected, or `FACE_UNVERIFIABLE` |
| FR-FACE-02 | Quality gate: minimum face size, sharpness, brightness, acceptable pose. Allow up to K recapture attempts (default 3) | M | Poor images are rejected with a reason |
| FR-FACE-03 | Compute a face embedding and compare with the registered owner's embedding(s) using cosine distance and a configurable threshold | M | Score and threshold stored with the session |
| FR-FACE-04 | Outcomes are exactly `MATCH`, `MISMATCH`, `UNVERIFIABLE`; `UNVERIFIABLE` goes to operator review and is **never** treated as `MISMATCH` or `MATCH` | M | Verified by unit tests |
| FR-FACE-05 | Support several reference images per owner (use best similarity) | S | Enrolment accepts 1–5 images |
| FR-FACE-06 | Store embeddings for matching; store evidence images only per the retention policy | M | Purge job removes expired images |
| FR-FACE-07 | Basic liveness check (e.g. blink or head-turn) to resist photo spoofing | C | Photo-of-photo test is rejected |

### 4.5 Watchlist Screening (FR-WL)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-WL-01 | On `MISMATCH`, and **before** the owner is notified, compare the driver's embedding against `wanted_list` and `missing_reports` (1:N) | M | Both tables searched in every mismatch case |
| FR-WL-02 | Use a watchlist threshold **stricter** than the owner-verification threshold; return the top-K candidates (default K = 3) with scores | M | Thresholds independently configurable |
| FR-WL-03 | Any candidate above threshold creates a review case in state `PENDING_HUMAN`; **no automatic police alert**; the owner notification is held while pending | M | Verified by test (M6) |
| FR-WL-04 | Distinguish `WANTED_MATCH` from `MISSING_PERSON_MATCH` with separate alert templates and priorities | M | Different alert types in the dashboard |
| FR-WL-05 | Configurable scope: `mismatch_only` (default) or `all_faces` (screen every captured driver, including owner matches) | S | Switch in config; documented as open decision D-02 |

### 4.6 Human Confirmation (FR-HC)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-HC-01 | Review queue for police operators showing: driver image, candidate image(s), similarity score, plate, location, time | M | All fields visible on one screen |
| FR-HC-02 | Operator actions: **Confirm** (dispatch police alert) or **Reject** (not a match → continue to owner notification) | M | Exactly one decision per case |
| FR-HC-03 | Record operator ID, decision, timestamp and optional note in the audit log | M | Entry is append-only |
| FR-HC-04 | Cases unresolved after a configurable time stay `PENDING` and are highlighted; they are **never** auto-dispatched | S | No auto-dispatch path exists in code |
| FR-HC-05 | The same queue also handles `NO_PLATE`, `FACE_UNVERIFIABLE`, fuzzy plate matches, low-confidence OCR and owner timeouts | M | Each case shows its reason code |

### 4.7 Owner Confirmation (FR-OWN)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-OWN-01 | Store owner contact channels (Telegram chat ID, phone, email) in the owner record | M | Present in dummy data |
| FR-OWN-02 | On mismatch with no watchlist hit (or hit rejected), send the owner a notification with plate, time, location, driver snapshot and two actions: **Allow**, **Complain** | M | Message received with both buttons |
| FR-OWN-03 | **Allow** → case closed as `AUTHORIZED_DRIVER`, logged, no police alert | M | Case state updated |
| FR-OWN-04 | **Complain** → HIGH `UNAUTHORIZED_USE` alert to the nearest police station | M | Alert created and routed |
| FR-OWN-05 | Configurable response timeout (production default 10 min; demo default 2 min). On timeout the case moves to the operator review queue (**open decision D-01**) | M | Timeout path covered by test |
| FR-OWN-06 | Owner responses are authenticated (bot chat-ID binding or signed one-time token), single-use and expire | M | Replayed or forged responses are rejected |
| FR-OWN-07 | Only the first response counts; later responses are ignored and logged | S | Idempotency test passes |

### 4.8 Alerts and Notifications (FR-ALR)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-ALR-01 | Alert payload contains alert ID, type, severity, plate, checkpoint, coordinates, timestamp, reason code, scores and evidence images | M | Schema validated |
| FR-ALR-02 | Alert types: `UNREGISTERED_VEHICLE`, `STOLEN_VEHICLE`, `MISSING_VEHICLE`, `BLACKLISTED_VEHICLE`, `UNAUTHORIZED_USE`, `WANTED_PERSON_MATCH`, `MISSING_PERSON_MATCH`, `EXPIRED_REGISTRATION` | M | Each type produced by a test scenario |
| FR-ALR-03 | Deliver to the nearest station by dashboard plus email (SMTP); SMS (Twilio) optional | M | Email received or logged in simulated mode |
| FR-ALR-04 | Reliable delivery using an outbox with retry and exponential back-off | M | No loss after a simulated network outage |
| FR-ALR-05 | De-duplicate: same plate + same alert type within a cooldown (default 15 min) merges into one alert | S | Second detection increments a counter |
| FR-ALR-06 | **Simulated mode** sends alerts to a mock station inbox; real channels are enabled by config | M | Demo works with no external services |
| FR-ALR-07 | Track station acknowledgement: `SENT → DELIVERED → ACKNOWLEDGED → RESOLVED` | S | Status visible on dashboard |

### 4.9 Geo-location and Routing (FR-GEO)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-GEO-01 | Maintain a checkpoint registry with name and coordinates | M | Each session tagged with a checkpoint |
| FR-GEO-02 | Maintain a police-station table; select the nearest station by great-circle (Haversine) distance | M | Correct station for all test checkpoints |
| FR-GEO-03 | Optionally use the phone's GPS instead of fixed checkpoint coordinates | C | Falls back to the checkpoint if unavailable |

### 4.10 Dashboard (FR-DSH)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-DSH-01 | Login with role-based access | M | Unauthorised pages blocked |
| FR-DSH-02 | Live feed of recent detections with outcome badges | M | Updates within 5 s |
| FR-DSH-03 | Alerts page with filters (type, severity, status, date, station) | M | Filters return correct rows |
| FR-DSH-04 | Review queue page (FR-HC) | M | Confirm/Reject work end-to-end |
| FR-DSH-05 | Search by plate, date and outcome; detail view with evidence and all scores | M | Detail shows reason codes |
| FR-DSH-06 | Show match confidence scores and thresholds used | S | Visible in detail view |
| FR-DSH-07 | Analytics: outcomes per day, hourly pattern, top flagged plates, alert map | S | Charts render from real data |
| FR-DSH-08 | Export logs and reports to CSV (and PDF if time permits) | S | File downloads correctly |

### 4.11 Administration and Data (FR-ADM)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-ADM-01 | Manage vehicles, owners (with face enrolment), `wanted_list`, `missing_reports`, stations and checkpoints via admin UI or scripts | M | CRUD operations succeed |
| FR-ADM-02 | Reproducible seed script that builds the full dummy database | M | One command rebuilds the dataset |
| FR-ADM-03 | Configuration panel (or file) for thresholds, timeouts, cooldowns and scope | S | Changes apply without code edits |
| FR-ADM-04 | Retention job purges evidence images older than the retention period (default 30 days) | M | Verified with back-dated test data |

### 4.12 Logging, Audit and Evaluation (FR-LOG)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-LOG-01 | Log every session: plate, scores, outcome, reason codes, timings | M | Row per session |
| FR-LOG-02 | Append-only audit log for operator, owner and admin actions (optionally hash-chained) | M | No update/delete path |
| FR-LOG-03 | Evaluation script outputs precision, recall, OCR accuracy, FAR/FRR and latency tables | M | Produces report-ready tables |

### 4.13 Authentication and Authorisation (FR-AUTH)

| ID | Requirement | Pri | Acceptance criteria |
|---|---|---|---|
| FR-AUTH-01 | Roles: Admin, Police Operator, Checkpoint Operator, Viewer | M | Permission matrix enforced |
| FR-AUTH-02 | Passwords stored hashed (bcrypt/argon2); token-based API sessions | M | No plaintext secrets in DB |
| FR-AUTH-03 | Session timeout and logout | S | Idle session expires |

## 5. Decision Matrix (Authoritative Business Rules)

| # | Plate result | Face result | Watchlist | Human / owner step | Outcome | Severity |
|---|---|---|---|---|---|---|
| 1 | No valid plate or low OCR confidence | — | — | Operator review | `NO_PLATE` / `LOW_CONFIDENCE` | Review |
| 2 | Not in registry | — | — | — | Police alert `UNREGISTERED_VEHICLE` | HIGH |
| 3 | `STOLEN` / `MISSING` / `BLACKLISTED` | — | — | — | Police alert (flag-specific type) | HIGH |
| 4 | `TEMP_EXPIRED` | continue to face check | — | — | Dashboard alert `EXPIRED_REGISTRATION`, then continue | MEDIUM |
| 5 | Valid (permanent or valid temporary) | `MATCH` | (skipped unless scope = `all_faces`) | — | **PASS**, logged | INFO |
| 6 | Valid | `UNVERIFIABLE` | — | Operator review | `FACE_UNVERIFIABLE` | Review |
| 7 | Valid | `MISMATCH` | Candidate found | Operator **Confirm** | Police alert `WANTED_PERSON_MATCH` or `MISSING_PERSON_MATCH` | HIGH |
| 8 | Valid | `MISMATCH` | Candidate found | Operator **Reject** | Continue to row 9 | — |
| 9 | Valid | `MISMATCH` | No candidate | Owner **Allow** | `AUTHORIZED_DRIVER`, logged | INFO |
| 10 | Valid | `MISMATCH` | No candidate | Owner **Complain** | Police alert `UNAUTHORIZED_USE` | HIGH |
| 11 | Valid | `MISMATCH` | No candidate | Owner timeout | Operator review (D-01) | Review |

> **Safety rule:** an outcome of "unverifiable", "no plate" or "timeout" can only lead to *review*, never to a pass and never to an automatic police alert.
>
> **Tipping-off rule:** while a watchlist candidate is pending human review, the owner is **not** notified.

## 6. Non-Functional Requirements (NFR)

### 6.1 Performance

| ID | Requirement | Target |
|---|---|---|
| NFR-PERF-01 | Plate recognition result after the plate is stable in view | ≤ 3 s (GPU), ≤ 6 s (CPU) |
| NFR-PERF-02 | Face capture to verification result | ≤ 2 s |
| NFR-PERF-03 | End-to-end decision (excluding human/owner wait) | ≤ 10 s |
| NFR-PERF-04 | Sustained processing rate on the dev laptop | ≥ 5 fps |
| NFR-PERF-05 | Dashboard page load with ≥ 10,000 log rows | ≤ 2 s |

### 6.2 Accuracy and Correctness

| ID | Requirement | Target |
|---|---|---|
| NFR-ACC-01 | Plate detection recall (daylight) | ≥ 90% |
| NFR-ACC-02 | Plate OCR exact-match | ≥ 85% |
| NFR-ACC-03 | Face verification TAR at FAR ≤ 1% | ≥ 90% |
| NFR-ACC-04 | Watchlist false matches are measured and reported; none dispatch without human review | Reported |
| NFR-ACC-05 | No silent failures: every non-pass state has a reason code | 100% |
| NFR-ACC-06 | Decision engine is deterministic: same inputs and config give the same outcome | 100% |

### 6.3 Reliability and Availability

| ID | Requirement |
|---|---|
| NFR-REL-01 | Alert delivery retried at least 5 times with exponential back-off, then flagged `FAILED` on the dashboard |
| NFR-REL-02 | Stream interruption does not crash the pipeline; auto-reconnect within 10 s |
| NFR-REL-03 | Database writes for a session are transactional (no half-written outcomes) |
| NFR-REL-04 | Health-check endpoint reports status of models, database, stream and notifier |
| NFR-REL-05 | A failing external service (Telegram, SMTP, Twilio) must not block detection or decisioning |

### 6.4 Security

| ID | Requirement |
|---|---|
| NFR-SEC-01 | Secrets (API keys, SMTP password, bot token) kept in environment variables / `.env`, never committed to the repository |
| NFR-SEC-02 | Passwords hashed (bcrypt/argon2); minimum password policy enforced |
| NFR-SEC-03 | Embeddings and evidence images served only through authenticated endpoints |
| NFR-SEC-04 | Owner-action tokens are signed, single-use and expire no later than the response timeout |
| NFR-SEC-05 | Strict input validation on every API endpoint (typed request models) |
| NFR-SEC-06 | Rate limiting on public-facing endpoints (e.g. owner response link) |
| NFR-SEC-07 | HTTPS for anything exposed beyond the local network |
| NFR-SEC-08 | Dependency vulnerability scan (`pip-audit`) before the final demo |

### 6.5 Privacy and Compliance

| ID | Requirement |
|---|---|
| NFR-PRV-01 | Only consented volunteer data or synthetic/public-licensed datasets; consent records retained |
| NFR-PRV-02 | Data minimisation: embeddings for matching; evidence images purged after the retention period (default 30 days) |
| NFR-PRV-03 | Purpose limitation: data used only for the functions defined in this PRD |
| NFR-PRV-04 | Right to removal: an admin can delete a person's face data on request, including embeddings and evidence |
| NFR-PRV-05 | Every watchlist-driven action has a recorded human decision (HITL) |
| NFR-PRV-06 | Role-based access limits who can see faces and watchlist data |

### 6.6 Usability

| ID | Requirement |
|---|---|
| NFR-USA-01 | A new operator can run a checkpoint session after ≤ 5 minutes of instruction |
| NFR-USA-02 | Outcomes use clear colour-coded badges (PASS / REVIEW / ALERT) plus text, not colour alone |
| NFR-USA-03 | Owner notification is readable on a phone screen and requires one tap to respond |
| NFR-USA-04 | Error messages state what happened and what to do next |

### 6.7 Maintainability and Testability

| ID | Requirement |
|---|---|
| NFR-MNT-01 | Modular code with clear interfaces between capture, vision, decision, notification and storage |
| NFR-MNT-02 | Decision engine has 100% branch coverage against the matrix in §5; overall unit-test coverage ≥ 70% |
| NFR-MNT-03 | Type hints, linting (ruff) and formatting (black) enforced in CI/pre-commit |
| NFR-MNT-04 | Recorded-session replay mode gives deterministic, repeatable tests |
| NFR-MNT-05 | All thresholds and timeouts are configuration, not hard-coded |

### 6.8 Portability and Compatibility

| ID | Requirement |
|---|---|
| NFR-POR-01 | Runs on Windows 10/11 and Ubuntu 22.04+ with Python 3.10 or 3.11 |
| NFR-POR-02 | Works with any phone camera app that exposes an MJPEG/RTSP stream; webcam fallback |
| NFR-POR-03 | Optional Docker setup for repeatable environments |

### 6.9 Observability and Explainability

| ID | Requirement |
|---|---|
| NFR-OBS-01 | Structured logs with a correlation (session) ID on every line |
| NFR-OBS-02 | Stage timings recorded per session (capture, detect, OCR, face, decision) |
| NFR-OBS-03 | Every decision stores reason codes and the scores/thresholds behind them |

### 6.10 Scalability (Design Headroom)

| ID | Requirement |
|---|---|
| NFR-SCL-01 | The prototype serves one active checkpoint, but the data model supports multiple checkpoints and stations |
| NFR-SCL-02 | Storage and search layers are replaceable (SQLite → PostgreSQL; NumPy → FAISS) without changing business logic |

### 6.11 Ethical Requirements

| ID | Requirement |
|---|---|
| NFR-ETH-01 | Face-verification performance is evaluated across varied lighting, angles and accessories, and results are reported honestly, including failures |
| NFR-ETH-02 | The report states the limitations and the potential for bias in face models |
| NFR-ETH-03 | The system is positioned as decision support; humans make all watchlist-based decisions |

## 7. Data Requirements

| Dataset | Minimum size (prototype) | Source | Notes |
|---|---|---|---|
| Plate images (detector training/validation) | 500–1,000 labelled | Public datasets + own photos of dummy plates | Check dataset licences |
| Plate test set (held out) | ≥ 100 images, varied angle/light/blur | Own captures | Never used for training |
| Vehicles (registry) | ~20–30 records | Manually created | Include permanent, temporary valid/expired, stolen, missing, blacklisted |
| Owners with faces | 8–12 consenting volunteers | Volunteers | 3–5 reference images each |
| Family/other drivers | 4–6 consenting volunteers | Volunteers | For Allow/Complain scenarios |
| `wanted_list` | 3–5 | Consenting volunteers or synthetic faces | **No real wanted persons** |
| `missing_reports` | 3–5 | Consenting volunteers or synthetic faces | **No real missing persons** |
| Police stations / checkpoints | 3 / 2 | Manually created | Real-looking coordinates, fictional names allowed |

## 8. Assumptions, Dependencies and Constraints

- Phone and laptop are on the same Wi-Fi network (or USB tethering) during the demo.
- Owner Telegram chat IDs are pre-registered in the dummy data.
- `missing_reports` is interpreted as **missing-person** records with reference face images (assumption A4).
- Free-tier services only (Telegram Bot API, SMTP, Twilio trial limited to verified numbers).
- All external dependencies (models, libraries) are installed and tested **before** Phase 2 to avoid late environment issues.

## 9. Acceptance Scenarios

Each scenario must be demonstrated and its result recorded in the evaluation report.

| ID | Scenario | Expected result |
|---|---|---|
| S01 | Registered vehicle, owner driving | PASS, logged |
| S02 | Registered vehicle, family member driving, owner taps **Allow** | `AUTHORIZED_DRIVER`, no police alert |
| S03 | Registered vehicle, stranger driving, owner taps **Complain** | HIGH `UNAUTHORIZED_USE` alert to nearest station |
| S04 | Plate not in registry | HIGH `UNREGISTERED_VEHICLE` alert |
| S05 | Plate marked `STOLEN` | HIGH `STOLEN_VEHICLE` alert |
| S06 | Plate marked `MISSING` | HIGH `MISSING_VEHICLE` alert |
| S07 | New car on valid temporary registration, owner driving | PASS (no false alert) |
| S08 | Temporary registration expired | MEDIUM `EXPIRED_REGISTRATION`, flow continues |
| S09 | Mismatch, driver matches `wanted_list`, operator **Confirms** | HIGH `WANTED_PERSON_MATCH`; owner **not** notified |
| S10 | Same as S09 but operator **Rejects** | Owner notified; Allow/Complain flow follows |
| S11 | Mismatch, driver matches `missing_reports` | Review case → on Confirm, `MISSING_PERSON_MATCH` alert |
| S12 | No plate visible | `NO_PLATE` → operator review, no alert |
| S13 | Face hidden (mask/tint/low light) | `FACE_UNVERIFIABLE` → operator review |
| S14 | Owner does not respond within timeout | Moves to operator review |
| S15 | Same flagged vehicle seen twice within cooldown | Single merged alert |
| S16 | Network down during alert, restored later | Alert delivered after retry |
| S17 | Photo of owner's face shown to camera (if liveness implemented) | Rejected |
| S18 | Cloned plate: valid plate on a different vehicle, different driver | Mismatch path triggered |

## 10. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | OCR accuracy low on Indian plates (fonts, dirt, tilt) | Medium | High | Fine-tune detector; position-aware correction; multi-frame voting; format validation | Dev |
| R2 | Face match unreliable (angle, glasses, lighting) | High | High | Quality gate; multiple reference images; UNVERIFIABLE state; tune threshold on own data | Dev |
| R3 | False watchlist match | Medium | High | Strict threshold; mandatory human confirmation | Dev |
| R4 | TensorFlow/PyTorch dependency conflicts | Medium | Medium | Isolated virtual env; install and test early; fallback to InsightFace/ONNX | Dev |
| R5 | Phone-to-laptop streaming latency or drops | Medium | Medium | Same LAN or USB tethering; auto-reconnect; recorded-session fallback | Dev |
| R6 | External service limits (Twilio trial, Gmail SMTP) | High | Low | Simulated mode; Telegram as primary free channel | Dev |
| R7 | Scope creep | Medium | High | MoSCoW priorities; MVP cut line in [phase_definition.md](phase_definition.md) | Dev |
| R8 | Privacy or ethics concerns raised by examiners | Medium | Medium | Consent forms, synthetic data, HITL, limitations section | Dev |
| R9 | Demo-day failure | Medium | High | Recorded replay mode; backup video; pre-demo checklist | Dev |

## 11. Out of Scope / Future Work

- Multi-camera fusion and tracking of a flagged vehicle across junctions
- Night-vision / IR support
- Integration with real databases (Vahan, CCTNS) under official authorisation
- Mobile app for owners and citizens (Telegram is used in the prototype)
- Blockchain-based tamper-proof logging (hash-chained audit log is the prototype step)
- Edge AI deployment
- Insurance / PUC / pending-challan checks
- Vehicle make/model/colour clone detection (data fields reserved, FR-REG-06)

## 12. Open Decisions

| ID | Question | Current default | Needs decision from |
|---|---|---|---|
| D-01 | What happens when the owner does not respond in time? | Move to operator review (no automatic police alert) | Project owner / guide |
| D-02 | Should watchlist screening run on **every** driver face or only on mismatches? | Mismatch only (matches stated workflow). Recommended to consider `all_faces`, because a wanted person may be driving their own vehicle | Project owner |
| D-03 | Should a "stolen/missing" plate alert wait for operator confirmation? | No — automatic when OCR confidence is above the gate | Project owner / guide |
| D-04 | Does `missing_reports` mean missing **persons** (assumed) or missing **vehicles**? | Persons | Project owner |

## 13. Traceability

Requirement groups map to modules in [architecture.md](architecture.md) and to delivery phases in [phase_definition.md §16](phase_definition.md).

## 14. Revision History

| Version | Date | Change |
|---|---|---|
| 1.0 | 04 Oct 2026 | First complete draft derived from the VehiLence project report and agreed workflow changes (owner Allow/Complain, watchlist screening with human confirmation) |
