# Dataset and Model Log — VehiGuard

Record the source, licence and use of **every** dataset, model or image collection used in the project. Update this file whenever you add one.

> **Privacy rule:** do **not** write volunteers' names or their real plate numbers in this file or anywhere in the GitHub repository. Use codes only (V01, V02, ...). Keep the code-to-name and code-to-plate list in a separate private file outside the repo.

## 1. Datasets and models

| ID | Name | Source / link | Licence (check it) | Used for | Size | Date added | Notes |
|---|---|---|---|---|---|---|---|
| D01 | YOLOv8n pre-trained weights (`yolov8n.pt`) | Ultralytics | AGPL-3.0 (verify) | Vehicle detection and vehicle type; base for plate detector | — | 2026-10 | Trained on COCO; not committed to Git |
| D02 | Public licence-plate dataset | [fill in link] | [fill in] | Training the plate detector | [number] images | [date] | Check the licence allows academic use |
| D03 | Own plate and vehicle photos/videos | Taken by me with my phone | Own work | Plate detector tests and extra training; scenario recordings | [number] images / clips | [date] | Parked vehicles with permission; held-out test set kept separate |
| D04 | Volunteer vehicle photos/videos | Consenting volunteers | Consent form ([consent_form.md](consent_form.md)) | Registry vehicles, scenario recordings (genuine, stolen, missing, pretend clone) | [number] vehicles | [date] | Stored locally only; **not in Git**; faces cropped or blurred in anything shown |
| D05 | Public vehicle images with colour/type labels (if needed) | [fill in link] | [fill in] | Appearance test set (type and colour family) | [number] | [date] | Only if own captures are not enough |
| D06 | Ultralytics sample image `bus.jpg` | Ultralytics docs | See Ultralytics | Phase 0 smoke test only | 1 image | 2026-10 | Not committed |
| D07 | Nepal plate detector (YOLOv8s) | https://huggingface.co/krishnamishra8848/Nepal-Vehicle-License-Plate-Detection | Apache-2.0 | Plate detection baseline | 22.5 MB | 2026-10 | Trained on Nepal plates; tested on my own Indian plate photos before relying on it; not committed to Git |
| D08 | Own dummy database (seed script) | Written by me in `scripts/seed_data.py` | Own work | Registry vehicles, stolen/missing reports, police stations, cameras (assigned coordinates), users | [number] vehicles, [number] reports | [date] | Fictional owners, FIR references and station names; camera coordinates are assigned (simulated) |
| D09 | PaddleOCR pre-trained models | PaddleOCR (installed with the library) | Apache-2.0 (verify) | Plate text recognition | — | [date] | Version pinned in `requirements.lock`; not committed to Git |
| D10 | EasyOCR pre-trained models | EasyOCR (downloaded on first use) | Apache-2.0 (verify) | OCR fallback | — | [date] | Not committed to Git |
| D11 | Scenario recordings S01–S17 | Recorded by me | Own work | Replay mode and evaluation | [number] clips / image sets | [date] | One set per scenario in `data/test_sessions/`; local only |

## 2. Data splits (fill in during Phases 2 and 5)

| Dataset | Train | Validation | **Test (never used for training)** |
|---|---|---|---|
| Plate images (D02 + D03) | [n] | [n] | **at least 100** |
| Vehicle crops for type and colour (D03 + D04 + D05) | — | — | **at least 100**, hand-labelled |
| Scenario recordings (D11) | — | — | [n] clips covering S01–S17 |

## 3. Volunteer register (codes only)

| Code | Vehicle type | Role in test data | Consent signed (Y/N) | Date | Photos / clips | Real plate stored (Y/N) | Photos in report/demo allowed (Y/N) | Withdrawal requested (Y/N) |
|---|---|---|---|---|---|---|---|---|
| V01 | | Genuine vehicle | | | | | | |
| V02 | | Genuine vehicle | | | | | | |
| V03 | | Fictional stolen | | | | | | |
| V04 | | Fictional missing | | | | | | |
| V05 | | Pretend clone test (genuine owner) | | | | | | |

Add rows as volunteers join. Roles are make-believe and only used in the dummy database.

## 4. Storage and retention

| Item | Location | Committed to Git? | Delete by |
|---|---|---|---|
| Volunteer vehicle photos and clips | `data/` (local only) | **No** (ignored by `.gitignore`) | 30 days after final evaluation |
| Evidence images (runtime) | `data/evidence/` (local only) | **No** | 30 days (open cases excepted) while running; all removed 30 days after final evaluation |
| PostgreSQL database and backups (`*.dump`, `*.sql`) | Local | **No** | Same |
| Signed consent forms | Private folder (paper or scan) | **No** | After the deletion date |
| Code-to-name and code-to-plate list | Private file outside the repo | **No** | After the deletion date |
| Model weights (`*.pt`) | Local | **No** | — |

## 5. Change log

| Date | Change |
|---|---|
| 2026-10 | File created for the VehiLence project |
| 2026-11-09 | Project changed to VehiGuard. Face photo entries (old D04, D05) removed. D04 now covers volunteer vehicles. Added D05 (appearance images), D08 (own dummy database), D09 and D10 (OCR models) and D11 (scenario recordings). Storage table updated for PostgreSQL and vehicle data |
