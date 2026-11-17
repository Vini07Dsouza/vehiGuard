# Technology Stack — VehiGuard

| Field | Value |
|---|---|
| Document | `tech_stack.md` |
| Version | 2.0 (Draft for review) |
| Date | 09 Nov 2026 |
| Author | [Vinisha Marina Dsouza] |
| Related documents | [problem_statement.md](problem_statement.md) · [prd.md](prd.md) · [architecture.md](architecture.md) · [phase_definition.md](phase_definition.md) |

## 1. Selection Principles

1. **Free and open source** wherever possible (budget constraint C2).
2. **Python for everything except the dashboard** — one language for vision, analysis, backend and tests. The dashboard is React, as chosen for the project.
3. **Runs on a single laptop** with an optional GPU; no cloud dependency for the core flow.
4. **Replaceable components** — OCR, storage and notification channels can be swapped without changing business logic.
5. **Mature, well-documented libraries** with active communities, because the project timeline is short.

## 2. Stack at a Glance

| Layer | Choice | Role |
|---|---|---|
| Language | Python 3.10 / 3.11; JavaScript for the dashboard | All backend components; dashboard |
| Capture | Phone camera apps (DroidCam, Iriun Webcam or IP Webcam); OpenCV `VideoCapture` | Video sources |
| Vehicle & plate detection | YOLO (Ultralytics YOLOv8) | Locate vehicle and plate |
| Image processing | OpenCV, NumPy | Preprocessing, colour analysis |
| OCR | PaddleOCR (primary), EasyOCR (fallback), Tesseract (optional) | Read plate text |
| Appearance analysis | OpenCV (HSV colour), scikit-learn (k-means) | Vehicle colour family; type from the detector class |
| Geospatial analytics | Own Haversine function (PostGIS optional) | Distance between cameras, nearest station, journey check |
| Backend API | FastAPI + Uvicorn + Pydantic | REST API, business logic hosting |
| Database | PostgreSQL | Persistence |
| ORM / migrations | SQLAlchemy 2.x + Alembic + psycopg | Data access |
| Background jobs | APScheduler (in-process) | Retries, retention, camera health |
| Police alert delivery | SMTP email, dashboard, simulated inbox | Alert dispatch |
| Dashboard | React (Vite) + React Router + Leaflet + Recharts | Operator and admin UI |
| Config & secrets | `pydantic-settings`, YAML, `.env` | Thresholds and credentials |
| Logging | `loguru` or `structlog` | Structured logs |
| Testing | pytest, pytest-cov, scikit-learn metrics | Unit, integration, evaluation |
| Quality | ruff, black, pre-commit, pip-audit, npm audit | Code quality and security hygiene |
| Version control | Git + GitHub | Source and issue tracking |
| Model training | Google Colab / Kaggle notebooks (free GPU) | Fine-tune plate detector |
| Annotation | Roboflow (free tier) or Label Studio | Label plate images |
| Packaging (optional) | Docker + docker-compose | Repeatable environments |

### 2.1 Changes from the earlier VehiLence plan

| Earlier plan | VehiGuard | Reason |
|---|---|---|
| Face verification with DeepFace | Removed | The project no longer identifies people |
| Telegram owner Allow / Complain flow | Removed | No owner-driver check |
| EasyOCR primary | PaddleOCR primary, EasyOCR fallback | PaddleOCR chosen for the project; EasyOCR is already installed and works as a safety net |
| SQLite | PostgreSQL | Better fit for time-range and journey queries and for several writers (several cameras) |
| Streamlit dashboard | React dashboard | Chosen for the project; richer maps and detail pages |
| Phone via IP Webcam | Phone via DroidCam / Iriun / IP Webcam | Whichever works reliably on the project network (see §3.1) |
| Fine-tuned YOLO plate detector, YOLOv8n vehicle detector | Unchanged | Still the detection core |

Work already done under the earlier plan carries over: the virtual environment, OpenCV, the YOLOv8n test, pre-commit hooks, the Nepal plate-detector baseline and the consent/data-handling approach.

## 3. Detailed Choices and Rationale

### 3.1 Capture: phone cameras

| Item | Decision |
|---|---|
| Apps | **DroidCam** or **Iriun Webcam** (the phone appears as a webcam on the laptop, read with `cv2.VideoCapture(index)`), or **IP Webcam** (serves a stream over Wi-Fi, read with `cv2.VideoCapture("http://<phone-ip>:8080/video")`) |
| Connection | Same Wi-Fi network; **USB** connection if Wi-Fi latency is poor |
| Several cameras | Each camera has its own camera ID and its own worker thread. Free tiers of some apps may limit how many phones can connect; check this in Phase 0 |
| Fallback for a second location | Re-register one phone at a different location between sessions, or feed recorded video (replay mode) |
| Resolution | 1280×720 at 15–30 fps; process about 5 fps |
| Mounting | Phone on a tripod or holder |
| Timestamps | The **laptop clock** at frame arrival. Phone clocks are not used |

**Why not a custom mobile app?** It adds Android development effort with no benefit for the evaluation. A camera app gives the same input in minutes.

**Camera locations.** Each camera is registered with assigned latitude/longitude. Because the demo phones are physically close, these coordinates are **simulated** (for example, Camera A and Camera B are registered about 38 km apart). This is stated in the report.

### 3.2 Vehicle and plate detection: YOLO

| Item | Decision |
|---|---|
| Library | `ultralytics` |
| Vehicle detector | Pre-trained `yolov8n.pt` (COCO classes: car, motorcycle, bus, truck); the class also gives the vehicle **type** |
| Plate detector | `yolov8n` or `yolov8s` fine-tuned on a licence-plate dataset. The Nepal plate detector (dataset log D07) is a baseline to compare against |
| Training data | Public plate datasets (Roboflow Universe, Kaggle) plus own photos; **verify each dataset's licence** |
| Training setup | Image size 640, 50–100 epochs, standard augmentations (brightness, blur, rotation, perspective) |
| Evaluation | mAP@0.5, precision, recall on a held-out test set |
| Inference | GPU if available, otherwise CPU with `yolov8n` |

**Licence note:** Ultralytics YOLOv8 is released under **AGPL-3.0**. This is fine for an academic project; a commercial product would need to comply with AGPL or obtain a commercial licence.

### 3.3 OCR: PaddleOCR with EasyOCR fallback

| Item | Decision |
|---|---|
| Primary | **PaddleOCR** (needs the `paddlepaddle` package; use the CPU build unless a supported GPU is available) |
| Fallback | **EasyOCR** with allow-list `A–Z 0–9`; Tesseract (`--psm 7`, whitelist) is optional |
| Pre-processing | Grayscale → denoise (bilateral / non-local means) → CLAHE contrast → deskew / perspective warp → resize |
| Post-processing | Uppercase, strip separators, position-aware correction (letter vs digit slots), regex validation |
| Robustness | Multi-frame voting (N = 10) and a confidence gate |
| Version note | PaddleOCR's Python API differs between major versions. Pin the version that installs cleanly in Phase 0 and follow the documentation for that version |

**Indian plate patterns (configurable in `config/plate_patterns.yaml`):**

| Type | Example | Pattern (indicative) |
|---|---|---|
| Standard | `KA19AB1234` | `^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$` |
| BH series | `22BH1234AA` | `^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$` |

**Why a fallback engine?** If PaddlePaddle conflicts with another package, or reads a particular plate style poorly, EasyOCR (already installed) keeps the pipeline working. Compare both engines on the plate test set and record the results.

### 3.4 Appearance analysis

| Item | Decision |
|---|---|
| Vehicle type | From the YOLO class (car, motorcycle, bus, truck); majority over the voting frames |
| Colour | Crop the vehicle body region, convert to HSV, take the dominant colour (k-means or histogram), and map it to a **colour family**: white/silver/grey, black, red, blue, green, yellow/orange, brown, other |
| Why families | Lighting makes white, silver and grey look alike, so they are one family. This avoids false mismatches |
| Unknown | If the crop is too dark, too small or blurred, the value is `UNKNOWN`, which is never a mismatch |
| Comparison | Equal type and equal colour family → match; known values that differ → mismatch |
| Stretch | A pretrained CNN embedding of the vehicle crop (cosine similarity) as an extra signal (FR-APP-06) |

### 3.5 Geospatial analytics

| Item | Decision |
|---|---|
| Distance | Haversine (great-circle) function in Python, using the camera coordinates |
| Journey check | `d > MAX_PLAUSIBLE_SPEED_KMH × (Δt + TIME_TOLERANCE_S)`, with `d ≥ MIN_CLONE_DISTANCE_KM` (see [architecture.md §8.3](architecture.md)) |
| Nearest station | Haversine from the camera to each station; minimum wins |
| Why straight-line | Straight-line distance never exceeds road distance, so the rule cannot flag a journey that was actually possible because of a long road |
| Optional upgrade | PostgreSQL **PostGIS** for geospatial queries and `ST_Distance`; not required for the prototype |
| Map display | Leaflet with OpenStreetMap tiles on the dashboard (needs internet; a blank map with markers is the offline fallback) |

### 3.6 Backend: FastAPI

| Item | Decision |
|---|---|
| Framework | **FastAPI** with Uvicorn |
| Why not Flask | Typed request/response models (Pydantic), automatic OpenAPI docs, async support, built-in dependency injection for auth |
| Auth | OAuth2 password flow with JWT access tokens; `passlib[bcrypt]` for hashing |
| Validation | Pydantic v2 models for every endpoint |
| Rate limiting | `slowapi` on the login endpoint |
| Live updates | Server-Sent Events (or periodic polling) so the dashboard updates without refresh |
| Structure | Modular monolith: routers → services → repositories |

### 3.7 Database: PostgreSQL

| Item | Decision |
|---|---|
| Database | **PostgreSQL**, installed locally (installer or Docker) |
| Driver / ORM | `psycopg` with SQLAlchemy 2.x; Alembic migrations |
| Indexes | `sightings(plate_no, observed_at)` for the journey query; `alerts(status, created_at)` |
| Evidence files | Local folder `data/evidence/<yyyy>/<mm>/<sighting_id>/`, accessed only through the authenticated API |
| Backup | `pg_dump` plus the evidence folder; the seed script can rebuild everything |
| Why PostgreSQL | Strong time-range and index support for the sighting history; handles writes from several camera workers; PostGIS can be added later |
| Setup note | The installer is large. If the network is slow, download it early or use Docker only if it is already installed |

### 3.8 Alerts and notifications

| Channel | Used for | Choice | Notes |
|---|---|---|---|
| **Dashboard** | All alerts | React alerts page | Always available |
| **Email (SMTP)** | HIGH and MEDIUM alerts to the station | `smtplib` / `fastapi-mail` | Gmail needs an app password (2-step verification on) |
| **Simulated mode** | Demo safety | Writes to a mock station inbox table | Default for tests and demo fallback |
| **SMS** | Optional | Twilio trial | Only to verified numbers; not required |

Delivery goes through an **outbox** with retry and exponential back-off (FR-ALR-04).

### 3.9 Dashboard: React

| Item | Decision |
|---|---|
| Framework | **React** built with **Vite**; talks to FastAPI over REST (no direct database access) |
| Routing | React Router |
| Maps | Leaflet via `react-leaflet`: cameras, alerts and the journey line between two sightings |
| Charts | Recharts: sightings and alerts per day, hourly pattern, recovery pipeline |
| Pages | Live monitor · Alerts · Alert detail · Plate search and timeline · Reports and recovery · Review list · Analytics · Admin · Audit log |
| Auth | Login page → JWT kept in memory/session; page and button access by role |
| Auto-refresh | Server-Sent Events or polling every few seconds |
| Node.js | A current LTS release; check the Vite documentation for its minimum |

### 3.10 Background jobs

| Job | Purpose |
|---|---|
| Outbox retry | Re-send failed alerts with exponential back-off (FR-ALR-04) |
| Retention purge | Delete evidence older than the retention window, except open cases (FR-EVD-03) |
| Camera health | Mark cameras offline when no frame arrives (FR-CAP-07) |

**APScheduler** runs in-process. Celery/Redis would be overkill for a single-machine prototype.

### 3.11 Testing, quality and DevOps

| Area | Tool |
|---|---|
| Unit / integration tests | `pytest`, `pytest-cov`, `httpx` (API tests) |
| Decision-engine and clone-analyser tests | Table-driven tests from the PRD §5 matrix (100% branch coverage), including borderline distance/time values |
| Evaluation | `scikit-learn` (precision/recall), `matplotlib` / `seaborn` |
| Linting / format | `ruff`, `black`, `mypy` (optional) |
| Hooks | `pre-commit` |
| Security | `pip-audit`, `npm audit`, `.env` excluded via `.gitignore` |
| CI (optional) | GitHub Actions: lint + unit tests (models mocked) |
| Replay testing | Recorded video/image sessions fed through the pipeline |

## 4. Hardware and Environment

| Item | Minimum | Recommended |
|---|---|---|
| Laptop/PC | Quad-core CPU, 8 GB RAM | 16 GB RAM, NVIDIA GPU (4 GB+ VRAM) with CUDA |
| Storage | 10 GB free (models, datasets, evidence, database) | 30 GB SSD |
| Phone | Android 8+ (or iPhone), rear camera ≥ 8 MP | 12 MP+, tripod/holder; a second phone if the app allows |
| Network | Shared Wi-Fi (2.4/5 GHz) | Wi-Fi 5 GHz or USB connection |
| OS | Windows 10/11 or Ubuntu 22.04+ | Ubuntu or Windows 11 with WSL2 for Linux-first tooling |
| Training | Google Colab / Kaggle free GPU | Local GPU if available |

## 5. Dependency Manifest (Reference)

Package names only. After the first successful install, run `pip freeze > requirements.lock` and **pin exact versions** to avoid breakage before the demo.

```text
# requirements.txt (reference — pin versions after first working install)
# --- Vision ---
ultralytics
opencv-python
numpy
paddlepaddle
paddleocr
easyocr
pytesseract        # optional
scikit-learn
# --- Backend ---
fastapi
uvicorn[standard]
pydantic
pydantic-settings
sqlalchemy
alembic
psycopg[binary]
passlib[bcrypt]
python-jose[cryptography]
python-multipart
slowapi
apscheduler
httpx
# --- Quality / test ---
pytest
pytest-cov
matplotlib
pandas
ruff
black
pre-commit
pip-audit
loguru
```

```text
# dashboard/package.json dependencies (reference — pin versions after first working install)
react
react-dom
react-router-dom
leaflet
react-leaflet
recharts
vite                # dev dependency
```

**System packages:** PostgreSQL, Node.js (LTS), Tesseract OCR binary (optional), CUDA drivers if using a GPU.

## 6. Environment Setup (Reference)

Windows Command Prompt first; Linux/macOS alternatives are in the comments.

```bat
:: 1. Create an isolated environment (Python 3.10 or 3.11)
python -m venv .venv
.venv\Scripts\activate          :: Linux: source .venv/bin/activate

:: 2. Install dependencies
pip install -r requirements.txt

:: 3. Smoke-test the whole import chain (Phase 0 exit check)
python -c "import cv2, ultralytics, paddleocr, easyocr, fastapi, sqlalchemy, psycopg; print('OK')"

:: 4. Create the database (PostgreSQL must be installed and running)
psql -U postgres -c "CREATE DATABASE vehiguard;"

:: 5. Configure secrets
copy .env.example .env          :: Linux: cp .env.example .env
:: set DATABASE_URL, JWT_SECRET, SMTP_* in .env

:: 6. Create tables and build the dummy database
alembic upgrade head
python scripts\seed_data.py

:: 7. Run the backend
uvicorn app.main:app --reload

:: 8. Run the dashboard (second terminal)
cd dashboard
npm install
npm run dev

:: 9. Start a camera worker (third terminal), by camera ID
python -m app.pipeline.run --camera CAM_A --source 0
:: or a stream URL:  --source http://<phone-ip>:8080/video
```

## 7. Licences and Costs

| Component | Licence (verify before redistribution) | Cost |
|---|---|---|
| Python, FastAPI, SQLAlchemy, Alembic | PSF / MIT | Free |
| OpenCV | Apache-2.0 | Free |
| Ultralytics YOLOv8 | **AGPL-3.0** | Free for academic use |
| PaddleOCR, PaddlePaddle | Apache-2.0 | Free |
| EasyOCR, Tesseract | Apache-2.0 | Free |
| scikit-learn | BSD-3-Clause | Free |
| PostgreSQL | PostgreSQL Licence | Free |
| psycopg | LGPL-3.0 | Free |
| React, Vite, Recharts | MIT | Free |
| Leaflet | BSD-2-Clause | Free |
| OpenStreetMap map tiles | Data under ODbL; follow the tile usage policy and show attribution | Free for light use |
| Gmail SMTP | Free personal tier (limits apply) | Free |
| Google Colab / Kaggle | Free tier with GPU quotas | Free |

Plate and vehicle datasets each carry their own licence; record the source and licence of every dataset in [datasets.md](datasets.md).

## 8. Technology Risks and Fallbacks

| Risk | Fallback |
|---|---|
| PaddlePaddle / PyTorch conflict | Use EasyOCR as primary behind the same `PlateOCR` interface; or run PaddleOCR in a separate environment |
| PaddleOCR reads Indian plates poorly | Compare with EasyOCR; improve preprocessing; fine-tune the detector crop quality |
| Phone stream unstable or only one phone connects | USB connection; laptop webcam; recorded video replay; re-register the single phone at a different location |
| YOLO plate model weak on Indian plates | Add more own images; increase augmentation; use `yolov8s` |
| PostgreSQL install or service problems | Use Docker if available; as a last resort run SQLite for development only (SQLAlchemy keeps the code the same) |
| Map tiles blocked offline | Show camera and alert markers on a plain background |
| SMTP limits | Simulated mode and the dashboard |
| GPU unavailable | `yolov8n`, lower resolution, fewer frames per second |

## 9. Revision History

| Version | Date | Change |
|---|---|---|
| 1.0 | 04 Oct 2026 | Stack selection for the earlier VehiLence idea |
| 2.0 | 09 Nov 2026 | Stack updated for VehiGuard: PaddleOCR, PostgreSQL, React, geospatial analytics; face, Telegram and Streamlit components removed |
