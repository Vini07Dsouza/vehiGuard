# Problem Statement — VehiGuard

**AI-Powered Stolen and Cloned Vehicle Detection Network**

| Field | Value |
|---|---|
| Document | `problem_statement.md` |
| Version | 2.0 (Draft for review) |
| Date | 09 Nov 2026 |
| Author | [Vinisha Marina Dsouza] |
| Project type | Final-year engineering project (proof of concept) |
| Related documents | [prd.md](prd.md) · [tech_stack.md](tech_stack.md) · [architecture.md](architecture.md) · [phase_definition.md](phase_definition.md) · [datasets.md](datasets.md) · [consent_form.md](consent_form.md) |

---

## 1. Background

Vehicle theft and the use of stolen or look-alike vehicles in other offences are a persistent challenge for law enforcement. Two situations are especially hard to handle at the roadside:

- **A stolen or missing vehicle** passes a camera or checkpoint and nobody notices, because the plate has to be read and looked up by a person.
- **A cloned number plate** is used. A criminal copies the registration number of a genuine vehicle onto a different vehicle. The plate is valid, it exists in the registry, and it is not on any stolen list, so a normal plate check passes it.

Automatic Number Plate Recognition (ANPR) automates the reading and lookup of plates. It answers one question: **"Is this plate known or flagged?"** It cannot answer the questions that matter for cloned plates:

- Can this plate really be in two places at once?
- Does the vehicle carrying this plate look like the vehicle that the plate is registered to?
- Has this vehicle been seen before, and where?

VehiGuard closes that gap. It is a network of cameras that reads plates, matches them against stolen and missing vehicle records, and compares observations across camera locations to find suspicious plates.

## 2. Problem Statement

> Stolen vehicles are hard to identify at the moment they pass a camera, and cloned registration plates cannot be caught by checking a plate against a list, because the plate itself is valid. Reviewing footage manually is slow, error-prone and cannot cover many locations, and when a suspicious vehicle is found there is usually no structured evidence (where, when, what it looked like) and no way to track what happened to the case afterwards.
>
> There is a need for an automated, low-cost system that reads vehicle number plates from several camera locations, matches them against stolen and missing vehicle records, identifies potentially cloned plates by detecting physically impossible journeys and appearance differences, collects location- and time-stamped evidence, alerts authorised police personnel, and tracks each case until the vehicle is recovered or the alert is closed.

## 3. Problem Analysis

### 3.1 Current practice and its limits

| Aspect | Typical current practice | Limitation |
|---|---|---|
| Plate reading | Manual reading, or single-camera ANPR | Each camera works alone; no cross-location view |
| Stolen-vehicle check | Plate looked up in a list by an operator or by software | Catches only plates already on the list |
| Cloned-plate detection | Rarely done automatically | A valid cloned plate passes every list check |
| Monitoring | Operators watching footage | Slow, fatigue-prone, not scalable |
| Evidence | Screenshots and notes collected afterwards | Inconsistent; location and time may be missing |
| Case follow-up | Phone calls and messages | No standard status, no audit trail |

### 3.2 Gap analysis

| ID | Gap | Consequence | How VehiGuard addresses it |
|---|---|---|---|
| G1 | Plate-only verification | A cloned but valid plate passes | Cross-location analysis of every sighting |
| G2 | No check that a plate cannot be in two places at once | Two vehicles with one plate go unnoticed | **Impossible-journey detection** using camera coordinates and timestamps |
| G3 | The vehicle is never compared with the registered description | A car wearing a motorcycle's plate passes | Vehicle type and colour compared with the registry and with earlier sightings |
| G4 | Manual, slow monitoring | Stolen vehicles missed or noticed late | Real-time ANPR and automatic matching against stolen and missing records |
| G5 | Evidence collected late and inconsistently | Weak support for investigation | Automatic evidence: images, camera, coordinates, timestamp |
| G6 | Alerts are unstructured and untracked | Slow, uninformed response | Alert to the nearest station with full evidence and a status workflow |
| G7 | No recovery tracking | Cases are forgotten or duplicated | **Recovery status tracking** from Reported to Recovered |
| G8 | No accountability trail | Decisions cannot be audited | Reason codes, scores and an append-only audit log |

### 3.3 Why compare locations and appearance

A plate lookup and a physical-consistency check fail in *different* ways. A cloned plate defeats the lookup, because it is a real registration number. But a plate number cannot belong to two vehicles that are 40 km apart and seen 5 minutes apart, and the cloned vehicle usually does not look like the registered one. Using several independent signals makes cloning much harder to hide, and no single weak signal triggers a police dispatch.

**Honest limits.** The system can only detect a clone when both the genuine vehicle and the clone pass monitored cameras, and when OCR reads the plate correctly. A plate that appears only once, or only at one camera, cannot be proven cloned by journey analysis. Appearance checks depend on lighting. For these reasons VehiGuard produces **suspected** clones for an officer to verify, never a final verdict.

## 4. Stakeholders Affected

| Stakeholder | Need |
|---|---|
| Police officer / control-room operator | Timely, evidence-backed alerts; clear reasons; a way to record what was done |
| Police station | Alerts routed by location with the evidence attached |
| Camera operator | Simple set-up of camera locations; clear camera health status |
| System administrator | Manage records, cameras, users, thresholds and data retention |
| Vehicle owner (indirect) | Quicker recovery of a stolen vehicle; protection from a plate clone being used in their name |
| General public | Reduced vehicle crime **and** protection of their personal data (plates, images) |

## 5. Objectives

| ID | Objective | Measure of success |
|---|---|---|
| O1 | Detect and read number plates from phone-camera streams at several camera locations | Plate detection and OCR accuracy meet the targets in [prd.md §3](prd.md) |
| O2 | Match plates against stolen and missing vehicle records | 100% correct classification on the scripted scenarios |
| O3 | Detect potentially cloned plates from physically impossible journeys across cameras | All clone scenarios flagged; no false clone alert on the genuine multi-camera test cases |
| O4 | Compare vehicle appearance (type, colour) with the registry and with earlier sightings | Type and colour accuracy meet the targets in [prd.md §3](prd.md) |
| O5 | Collect location- and time-stamped evidence for every flagged sighting | Every alert has images, camera, coordinates and timestamp |
| O6 | Generate alerts for authorised police personnel, routed to the nearest station | Correct station in all test cases; no lost alerts |
| O7 | Track recovery status and provide logging, a dashboard and evaluation metrics | All status changes and decisions traceable; precision, recall and latency reported |

## 6. Proposed Solution (Summary)

1. Phone cameras at several camera locations stream video to the VehiGuard core. Each camera is registered with a name and coordinates.
2. YOLO locates the vehicle and the plate; PaddleOCR reads the plate, validated across several frames.
3. The vehicle's type and colour are extracted.
4. The plate is checked against the vehicle registry and the stolen/missing records. A match raises a HIGH alert.
5. Every accepted plate is stored as a **sighting** (plate, camera, time, appearance, evidence).
6. The new sighting is compared with the plate's earlier sightings at other cameras. A physically impossible journey, or an appearance mismatch, raises a **suspected clone** alert.
7. Authorised police personnel receive the alert with evidence, work the case through the status workflow, and record recovery.
8. Everything is logged and visible on a dashboard.

Full detail: [architecture.md](architecture.md).

## 7. Scope

### 7.1 In scope (prototype)

- Phone-camera capture from two or more camera locations (or recorded video replay)
- Vehicle and plate detection, preprocessing, OCR, format validation, multi-frame voting
- Vehicle type and colour extraction and comparison
- **Own, manually created dummy database**: vehicles, stolen/missing reports, police stations, cameras
- Matching against stolen and missing vehicle records
- Sighting history and cross-camera clone detection (impossible journeys and appearance differences)
- Evidence collection with location and timestamp
- Alerts for authorised police personnel (dashboard; email; simulated delivery by default)
- Recovery status tracking
- React dashboard, logging, analytics and an evaluation report

### 7.2 Out of scope (prototype)

- Integration with real government or police databases (e.g. Vahan, CCTNS)
- Real stolen-vehicle data
- Deployment on real CCTV infrastructure or at real roadside locations
- Face recognition or any identification of people
- High-speed capture, full night-time or infrared operation, make/model recognition
- Automated enforcement; every police action stays with a human
- Legal-evidence-grade chain of custody

## 8. Assumptions and Constraints

| ID | Type | Statement |
|---|---|---|
| A1 | Assumption | One or more phones and a laptop are available on the same network for the demo |
| A2 | Assumption | The camera locations are registered with assigned coordinates. In the demo, the phones are physically close, so coordinates are **simulated** (the cameras are treated as if they were far apart) and this is stated in the report |
| A3 | Assumption | All timestamps are taken from the laptop's clock when each frame is received, so phone clocks do not matter |
| A4 | Assumption | Vehicles are slow-moving or stationary at the capture point, with the plate reasonably visible and in daylight |
| A5 | Assumption | A single phone may be re-registered at different locations between sessions, or recorded video may stand in for a second camera, if only one phone can stream at a time |
| C1 | Constraint | All data is dummy, consented or synthetic; no real stolen-vehicle data and no real personal data of third parties |
| C2 | Constraint | Budget limited to free or free-tier tools |
| C3 | Constraint | Must be demonstrable on a single laptop within the academic calendar |
| C4 | Constraint | OCR and appearance analysis are probabilistic; the system must never treat "unreadable" or "unknown" as a match or a mismatch |

## 9. Success Criteria

The project is successful if, in a live demo and a recorded evaluation:

1. All scripted scenarios in [prd.md §9](prd.md) produce the expected outcome.
2. Accuracy and latency figures meet, or are honestly reported against, the targets in [prd.md §3 and §6](prd.md).
3. A genuine vehicle seen at two cameras with a plausible journey is **not** flagged as a clone.
4. Every alert contains evidence (images, camera, coordinates, timestamp) and a reason code.
5. The limitations section of the report states clearly where the system does and does not work.

## 10. Ethical, Legal and Privacy Considerations

Number plates and vehicle images can be linked to people, so the project adopts these principles from the start:

- **Consent and dummy data.** Vehicle photos and plate numbers come only from consenting volunteers, the student's own captures, or public licensed datasets. The stolen/missing records are fictional. No real stolen-vehicle data is used.
- **No face recognition.** Faces that appear in frames are not detected, stored for matching or identified. Evidence images shown in reports are cropped or blurred where people are visible.
- **No fake plates on real vehicles.** Clone scenarios use images, video or paper printouts shown to the camera in a controlled test. A copied plate is never attached to a vehicle or used in public.
- **Human in the loop.** The system raises *leads*. A police officer verifies and decides; there is no automated enforcement.
- **Data minimisation.** Evidence images are kept for a limited, configurable period (default 30 days), except for cases still open.
- **Transparency and accountability.** Every alert stores reason codes, scores and the actor involved; every status change is logged.
- **Bias and error awareness.** OCR and colour detection perform unevenly across lighting, plate styles and dirt. The evaluation reports performance across varied conditions.
- **Legal context.** A real deployment would need explicit legal authority, a defined purpose and compliance with applicable Indian law, including the Digital Personal Data Protection Act, 2023. This prototype does not claim such authority.

## 11. Key Risks (Summary)

| Risk | Impact | Mitigation |
|---|---|---|
| OCR misreads a plate, creating a false match or false clone | Wrong alert | Format validation, multi-frame voting, confidence gate, fuzzy matches go to review only |
| Colour looks different under changing light | False appearance mismatch | Colour families, majority vote across frames, `UNKNOWN` is never a mismatch |
| Phone streams are unstable or only one phone can stream | Demo failure | Auto-reconnect, USB or Wi-Fi alternatives, recorded-video replay mode |
| Clone demo is not realistic with nearby phones | Weak demonstration | Assigned (simulated) coordinates, clearly documented; scripted recordings |
| Misuse of plate or image data | Privacy harm | Consented or dummy data only, role-based access, audit log, retention limits |

The full risk register is in [prd.md §10](prd.md).

## 12. Expected Deliverables

1. Working prototype (capture → detect → verify → analyse → alert → track → dashboard)
2. Dummy database and a reproducible seed script
3. Evaluation report (accuracy, clone-detection results, latency, limitations)
4. Documentation set: this document, PRD, tech stack, architecture, phase plan, dataset log, consent form
5. Final project report and demo

## 13. Glossary

| Term | Meaning |
|---|---|
| ANPR / ALPR | Automatic Number/License Plate Recognition |
| OCR | Optical Character Recognition: converting plate image text to characters |
| Cloned plate | A genuine registration number copied onto a different vehicle |
| Sighting | One recorded observation of a plate at a camera: plate, camera, time, appearance, evidence |
| Impossible journey | Two sightings of the same plate whose distance and time gap would need a speed above the plausible maximum |
| Appearance signature | Vehicle type and colour family extracted from a sighting |
| Haversine distance | Great-circle (straight-line over the earth) distance between two coordinates |
| Registry | The dummy table of registered vehicles with their type, make, model and colour |
| Stolen/missing report | A record that a registered vehicle has been reported stolen or missing |
| Recovery status | Where a stolen/missing case stands: Reported, Detected, Under Investigation, Recovered, Closed |
| Alert | A notification to authorised police personnel with severity, reason and evidence |
| HIGH / MEDIUM / LOW | Alert severity levels defined in [prd.md §5](prd.md) |
