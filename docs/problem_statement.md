# Problem Statement — VehiLence

**AI-Powered Vehicle Number Plate Detection, Driver Verification and Alert System**

| Field | Value |
|---|---|
| Document | `problem_statement.md` |
| Version | 1.0 (Draft for review) |
| Date | 04 Oct 2026 |
| Author | [Vinisha Marina Dsouza] |
| Project type | Final-year engineering project (proof of concept) |
| Related documents | [prd.md](prd.md) · [tech_stack.md](tech_stack.md) · [architecture.md](architecture.md) · [phase_definition.md](phase_definition.md) |

---

## 1. Background

Vehicle-related crime — theft, robbery, hit-and-run, and the use of stolen, cloned or unregistered vehicles in other offences — is a persistent challenge for law enforcement. At a checkpoint, an officer is expected to judge a vehicle within seconds, usually by looking at the plate and, at best, calling a control room to look up the number.

Automatic Number Plate Recognition (ANPR) automates part of this by reading the plate and looking it up in a database. It is useful, but it answers only one question: **"Is this plate known or flagged?"** It does not answer the questions that matter in practice:

- Is the person driving this vehicle the person it is registered to, or someone the owner has approved?
- Is the plate genuine, or has it been copied from another vehicle?
- Is the person behind the wheel someone the police are already looking for?

VehiLence is designed to close that gap by combining plate recognition with driver face verification and a human-supervised alert workflow.

## 2. Problem Statement

> Existing plate-based vehicle checks verify only the **number on the plate**, never **who is driving**. A vehicle carrying a valid or cloned plate, or being driven by an unauthorised person, passes unnoticed. Manual monitoring of footage is slow, error-prone and cannot scale, and alerts reach the nearest police station late or not at all.
>
> There is a need for an automated, low-cost system that reads a vehicle's number plate, confirms that the driver's face belongs to the registered owner (or a person the owner approves), screens unrecognised drivers against missing-person and wanted records under human supervision, and routes verified alerts to the nearest police station — while avoiding false alarms for legitimate situations such as newly purchased vehicles and family members driving.

## 3. Problem Analysis

### 3.1 Current practice and its limits

| Aspect | Typical current practice | Limitation |
|---|---|---|
| Vehicle identification | Manual reading of plate, or plate-only ANPR | Identity of the *driver* is never verified |
| Monitoring | Officers or operators watching footage | Slow, fatigue-prone, not scalable to city traffic volumes |
| Record lookup | Radio/phone call to control room | Delays; depends on the officer's availability |
| Alerting | Ad hoc calls and messages | No standard payload (location, time, images); no audit trail |
| Watchlist checks | Done separately, if at all | Not integrated at the point of detection |

### 3.2 Gap analysis

| ID | Gap | Consequence | How VehiLence addresses it |
|---|---|---|---|
| G1 | Plate-only verification | A vehicle with a cloned but valid plate passes the check | Driver's face must match the face on record for that plate |
| G2 | No driver identity check | Registered vehicle driven by an unauthorised person is not detected | Face verification against the registered owner |
| G3 | Manual, slow monitoring | Missed or late detection | Automated real-time detection and decisioning |
| G4 | Delayed, unstructured alerts | Police response is slower and less informed | Automatic alert to the **nearest** station with plate, location, timestamp and images |
| G5 | No watchlist cross-check at detection time | A wanted or missing person driving a vehicle is not flagged | Face screened against `wanted_list` and `missing_reports`, with **human confirmation** before any police dispatch |
| G6 | Legitimate edge cases cause false alarms | New cars (no permanent plate yet) and family drivers trigger alerts, causing alert fatigue | Temporary-registration support; **owner Allow / Complain** workflow |
| G7 | No accountability trail | Decisions cannot be audited or challenged | Full logging, reason codes and an append-only audit log |

### 3.3 Why a plate-plus-face approach

A plate lookup and a face match fail in *different* ways. A cloned plate defeats the plate lookup, but the cloner's face will not match the owner on record. A look-alike driver cannot fake a stolen-vehicle flag on the plate. Requiring both to agree makes impersonation and plate cloning much harder, which is the central design idea of the project.

## 4. Stakeholders Affected

| Stakeholder | Need |
|---|---|
| Police control-room operator | Fewer false alerts; clear evidence; ability to confirm or reject before dispatch |
| Police station | Timely, location-tagged, evidence-backed alerts |
| Vehicle owner | Control over who is flagged as driving their vehicle; no police action against family members |
| Checkpoint operator | Simple capture workflow; clear pass / review / alert outcome |
| System administrator | Manage records, thresholds, users and data retention |
| General public | Protection from vehicle crime **and** protection from misuse of their biometric data |

## 5. Objectives

| ID | Objective | Measure of success |
|---|---|---|
| O1 | Detect and read number plates from a live phone-camera feed | Plate-level OCR accuracy meets the target in [prd.md §3](prd.md) |
| O2 | Verify plate status against a registry (registered, temporary, stolen, missing, blacklisted) | 100% correct classification on the scripted test cases |
| O3 | Verify that the driver's face matches the registered owner | Face-verification accuracy meets the PRD targets on the volunteer test set |
| O4 | On mismatch, screen the driver against `missing_reports` and `wanted_list`, with human confirmation before dispatch | No police alert is sent from a watchlist match without an operator decision |
| O5 | Let the owner resolve a mismatch with **Allow** or **Complain** | Allow closes the case; Complain alerts police; every response is logged |
| O6 | Route alerts to the nearest police station with full evidence | Correct station selected in all test cases; alert includes plate, location, timestamp, images |
| O7 | Provide logging, a dashboard and evaluation metrics | All decisions traceable; precision, recall, FAR and FRR reported |

## 6. Proposed Solution (Summary)

1. A phone camera at a checkpoint streams video to the VehiLence core.
2. YOLOv8 locates the vehicle and number plate; OCR reads the plate, validated across several frames.
3. The plate is checked against the registry. Unregistered or flagged plates raise a police alert directly.
4. For a valid plate, the driver's face is captured and compared with the registered owner's face.
5. **Match** → pass (logged). **Mismatch** → the face is screened against `wanted_list` and `missing_reports`.
6. A watchlist candidate goes to a police operator for **human confirmation** before any alert. Otherwise the owner is notified and chooses **Allow** or **Complain**.
7. Everything is logged and visible on an admin dashboard.

Full detail: [architecture.md](architecture.md).

## 7. Scope

### 7.1 In scope (prototype)

- Phone-camera capture of plate and driver face
- Plate detection, preprocessing, OCR, format validation, multi-frame voting
- Registry verification with permanent and temporary registrations
- Face verification (1:1 against owner) and watchlist screening (1:N)
- Human-confirmation queue and owner Allow / Complain workflow
- Alert generation and routing to the nearest station (simulated delivery by default; email/SMS/Telegram channels supported)
- Dashboard, logging, analytics and evaluation report
- **Manually created dummy databases** built only from consented or synthetic data

### 7.2 Out of scope (prototype)

- Integration with real government or police databases (e.g. Vahan, CCTNS)
- Real wanted-person or missing-person data
- Deployment on real CCTV infrastructure or at real checkpoints
- High-speed vehicle capture, full night-time/IR operation, multi-camera tracking
- Production-grade liveness detection and legal-evidence-grade chain of custody

## 8. Assumptions and Constraints

| ID | Type | Statement |
|---|---|---|
| A1 | Assumption | A phone camera and a laptop on the same network are available for the demo |
| A2 | Assumption | The vehicle is stationary or slow-moving at the capture point, with the driver's face reasonably visible |
| A3 | Assumption | Owner contact details (e.g. Telegram chat) are pre-registered in the dummy database |
| A4 | Assumption | `missing_reports` holds records of missing **persons**, each with a reference face image |
| C1 | Constraint | All data is dummy, consented or synthetic; no real personal data of third parties is used |
| C2 | Constraint | Budget limited to free or free-tier tools |
| C3 | Constraint | Project must be demonstrable on a single laptop within the academic calendar |
| C4 | Constraint | Face matching is probabilistic; the system must never treat "unverifiable" as "verified" |

## 9. Success Criteria

The project is successful if, in a live demo and a recorded evaluation:

1. All scripted scenarios in [prd.md §9](prd.md) produce the expected outcome.
2. Accuracy and latency figures meet or are honestly reported against the targets in [prd.md §3 and §5](prd.md).
3. No watchlist-based alert is dispatched without a recorded human decision.
4. The limitations section of the report states clearly where the system does and does not work.

## 10. Ethical, Legal and Privacy Considerations

Face recognition on people is sensitive technology. The project adopts these principles from the start:

- **Consent and synthetic data.** Only volunteers who have given written consent, or publicly licensed/synthetic datasets, are used for faces. No real wanted or missing-person data is used.
- **Human in the loop.** The system *recommends*; a person decides before any watchlist-based police action.
- **Data minimisation.** Face **embeddings** are stored for matching; evidence images are kept for a limited, configurable period and then purged.
- **Transparency and accountability.** Every decision stores reason codes, scores and the actor involved.
- **Bias awareness.** Face models can perform unevenly across lighting, skin tones, ages and accessories. The evaluation reports performance across varied conditions and the report acknowledges the limitation.
- **Legal context.** A real deployment would require explicit legal authority, a defined purpose, and compliance with applicable Indian law, including the Digital Personal Data Protection Act, 2023. This prototype does not claim such authority.

## 11. Key Risks (Summary)

| Risk | Impact | Mitigation |
|---|---|---|
| Poor lighting, blur or angle degrades OCR and face matching | Wrong or missed decisions | Quality gates, multi-frame voting, "unverifiable → human review" |
| Tinted glass, masks, helmets hide the face | Face check impossible | Treated as `FACE_UNVERIFIABLE`, never as mismatch |
| False watchlist matches | Wrongful police action | Strict threshold plus mandatory human confirmation |
| Dependency or hardware problems near the demo | Demo failure | Early environment lock, recorded-session replay mode |
| Misuse of biometric data | Privacy harm | Consented/dummy data only, RBAC, audit log, retention limits |

The full risk register is in [prd.md §10](prd.md).

## 12. Expected Deliverables

1. Working prototype (capture → detect → verify → decide → alert → dashboard)
2. Dummy databases and a reproducible seed script
3. Evaluation report (accuracy, FAR/FRR, latency, limitations)
4. Documentation set: this document, PRD, tech stack, architecture, phase plan
5. Final project report and demo

## 13. Glossary

| Term | Meaning |
|---|---|
| ANPR / ALPR | Automatic Number/License Plate Recognition |
| OCR | Optical Character Recognition — converting plate image text to characters |
| Embedding | Numeric vector representing a face, used for similarity comparison |
| FAR | False Accept Rate — fraction of impostor attempts wrongly accepted |
| FRR | False Reject Rate — fraction of genuine attempts wrongly rejected |
| TAR | True Accept Rate = 1 − FRR |
| HITL | Human in the loop |
| Watchlist | Combined term for `wanted_list` and `missing_reports` |
| Temporary registration | Short-validity registration issued to a new vehicle before its permanent plate |
| RBAC | Role-based access control |
