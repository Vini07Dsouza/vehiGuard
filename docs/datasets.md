# Dataset and Model Log — VehiLence

Record the source, licence and use of **every** dataset, model or image collection used in the project. Update this file whenever you add one.

> **Privacy rule:** do **not** write volunteers' names in this file or anywhere in the GitHub repository. Use codes only (V01, V02, ...). Keep the code-to-name list in a separate private file outside the repo.

## 1. Datasets and models

| ID | Name | Source / link | Licence (check it) | Used for | Size | Date added | Notes |
|---|---|---|---|---|---|---|---|
| D01 | YOLOv8n pre-trained weights (`yolov8n.pt`) | Ultralytics | AGPL-3.0 (verify) | Vehicle detection; base for plate detector | — | 2026-10 | Trained on COCO; not committed to Git |
| D02 | Public licence-plate dataset | [fill in link] | [fill in] | Training the plate detector | [number] images | [date] | Check the licence allows academic use |
| D03 | Own plate photos | Taken by me with my phone | Own work | Plate detector tests and extra training | [number] images | [date] | Printed, toy or parked cars; held-out test set kept separate |
| D04 | Volunteer face photos | Consented volunteers | Consent form | Owner, driver, watchlist test data | [number] people | [date] | Stored locally only; **not in Git** |
| D05 | Synthetic or public face images (if needed) | [fill in link] | [fill in] | Fictional wanted / missing faces | [number] | [date] | Only if volunteers are not enough |
| D06 | Ultralytics sample image `bus.jpg` | Ultralytics docs | See Ultralytics | Phase 0 smoke test only | 1 image | 2026-10 | Not committed |

## 2. Data splits (fill in during Phase 2)

| Dataset | Train | Validation | **Test (never used for training)** |
|---|---|---|---|
| Plate images (D02 + D03) | [n] | [n] | **at least 100** |
| Face pairs (D04) | — | — | [n genuine pairs] / [n impostor pairs] |

## 3. Volunteer register (codes only)

| Code | Role in test data | Consent signed (Y/N) | Date | Photos | Photos in report/demo allowed (Y/N) | Withdrawal requested (Y/N) |
|---|---|---|---|---|---|---|
| V01 | Owner | | | | | |
| V02 | Owner | | | | | |
| V03 | Family / other driver | | | | | |
| V04 | Fictional wanted | | | | | |
| V05 | Fictional missing | | | | | |

Add rows as volunteers join. Roles are make-believe and only used in the dummy database.

## 4. Storage and retention

| Item | Location | Committed to Git? | Delete by |
|---|---|---|---|
| Volunteer photos | `data/faces/` (local only) | **No** (ignored by `.gitignore`) | 30 days after final evaluation |
| Face embeddings | Database (local) | **No** (`*.db` ignored) | Same |
| Signed consent forms | Private folder (paper or scan) | **No** | After the deletion date |
| Code-to-name list | Private file outside the repo | **No** | After the deletion date |
| Model weights (`*.pt`) | Local | **No** | — |

## 5. Change log

| Date | Change |
|---|---|
| 2026-10 | File created |
