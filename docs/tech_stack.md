# Technology Stack — VehiLence

| Field | Value |
|---|---|
| Document | `tech_stack.md` |
| Version | 1.0 (Draft for review) |
| Date | 04 Oct 2026 |
| Author | [Vinisha Marina Dsouza] |
| Related documents | [problem_statement.md](problem_statement.md) · [prd.md](prd.md) · [architecture.md](architecture.md) · [phase_definition.md](phase_definition.md) |

## 1. Selection Principles

1. **Free and open source** wherever possible (budget constraint C2).
2. **Python end-to-end** — one language for vision, backend, dashboard and tests.
3. **Runs on a single laptop** with an optional GPU; no cloud dependency for the core flow.
4. **Replaceable components** — storage, face model and notification channels can be swapped without changing business logic.
5. **Mature, well-documented libraries** with active communities, because the project timeline is short.

## 2. Stack at a Glance

| Layer | Choice | Role |
|---|---|---|
| Language | Python 3.10 / 3.11 | All components |
| Capture | Android phone + IP Webcam / DroidCam; OpenCV `VideoCapture` | Video source |
| Vehicle & plate detection | YOLOv8 (Ultralytics) | Locate vehicle and plate |
| Image processing | OpenCV, NumPy | Preprocessing, quality checks |
| OCR | EasyOCR (primary), Tesseract (fallback) | Read plate text |
| Face detection & embedding | DeepFace (Facenet512 + RetinaFace/MTCNN detector) | Face verification and watchlist matching |
| Similarity search | NumPy cosine (FAISS optional) | 1:1 and 1:N face matching |
| Backend API | FastAPI + Uvicorn + Pydantic | REST API, business logic hosting |
| ORM / DB | SQLAlchemy 2.x + SQLite (WAL mode) | Persistence |
| Background jobs | APScheduler (in-process) | Timeouts, retries, retention |
| Owner notification | Telegram Bot API (`python-telegram-bot` or `aiogram`) | Allow / Complain buttons |
| Police alert delivery | SMTP email (primary), Twilio SMS (optional), dashboard | Alert dispatch |
| Dashboard | Streamlit (+ Plotly / Folium for charts and maps) | Operator and admin UI |
| Config & secrets | `pydantic-settings`, YAML, `.env` | Thresholds and credentials |
| Logging | `loguru` or `structlog` | Structured logs |
| Testing | pytest, pytest-cov, scikit-learn metrics | Unit, integration, evaluation |
| Quality | ruff, black, pre-commit, pip-audit | Code quality and security hygiene |
| Version control | Git + GitHub | Source and issue tracking |
| Model training | Google Colab / Kaggle notebooks (free GPU) | Fine-tune plate detector |
| Annotation | Roboflow (free tier) or Label Studio | Label plate images |
| Packaging (optional) | Docker + docker-compose | Repeatable environments |

## 3. Detailed Choices and Rationale

### 3.1 Capture: Android phone camera

| Item | Decision |
|---|---|
| App | **IP Webcam** (serves an MJPEG stream over Wi-Fi) or **DroidCam**; both are free |
| Read in code | `cv2.VideoCapture("http://<phone-ip>:8080/video")` |
| Connection | Same Wi-Fi network; **USB tethering** if Wi-Fi latency is poor |
| Resolution | 1280×720 at 15–30 fps; process 5–10 fps |
| Mounting | Phone on a tripod or holder |
| Fallback | Laptop webcam, video file or image folder (FR-CAP-02) |

**Why not a custom mobile app?** It adds Android development effort with no benefit for the evaluation. A streaming app gives the same input in minutes. A browser-based capture page (`getUserMedia`) is a possible alternative, but mobile browsers require HTTPS, which adds setup work.

### 3.2 Vehicle and plate detection: YOLOv8

| Item | Decision |
|---|---|
| Library | `ultralytics` |
| Vehicle detector | Pre-trained `yolov8n.pt` (COCO classes: car, motorcycle, bus, truck) |
| Plate detector | `yolov8n` or `yolov8s` **fine-tuned** on a licence-plate dataset |
| Training data | Public plate datasets (Roboflow Universe, Kaggle) plus own photos; **verify each dataset's licence** |
| Training setup | Image size 640, 50–100 epochs, standard augmentations (brightness, blur, rotation, perspective) |
| Evaluation | mAP@0.5, precision, recall on a held-out test set |
| Inference | GPU if available, otherwise CPU with `yolov8n` |

**Why YOLOv8?** It gives a good accuracy/speed balance, has simple training and export workflows, and matches the project report.

**Licence note:** Ultralytics YOLOv8 is released under **AGPL-3.0**. This is fine for an academic project; a commercial product would need to comply with AGPL or obtain a commercial licence.

### 3.3 OCR: EasyOCR with Tesseract fallback

| Item | Decision |
|---|---|
| Primary | **EasyOCR** with allow-list `A–Z 0–9`, run on the preprocessed crop |
| Fallback | **Tesseract** (`--psm 7`, character whitelist) |
| Pre-processing | Grayscale → denoise (bilateral / non-local means) → CLAHE contrast → deskew / perspective warp → resize |
| Post-processing | Uppercase, strip separators, position-aware correction (letter vs digit slots), regex validation |
| Robustness | Multi-frame voting (N = 10) |

**Indian plate patterns (configurable in `config/plate_patterns.yaml`):**

| Type | Example | Pattern (indicative) |
|---|---|---|
| Standard | `KA19AB1234` | `^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$` |
| BH series | `22BH1234AA` | `^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$` |
| Temporary | state-specific | Defined in config, because formats vary by state and period |

**Why two engines?** EasyOCR is generally more robust on tilted or low-quality plates; Tesseract is lightweight and works as a cross-check or fallback.

### 3.4 Face verification: DeepFace

| Item | Decision |
|---|---|
| Library | `deepface` |
| Embedding model | **Facenet512** (512-d embedding) |
| Face detector | **RetinaFace** (more accurate) or **MTCNN**; OpenCV detector as fast fallback |
| Distance metric | Cosine distance |
| Thresholds | Start from the library's default for the chosen model, then **tune on the project's own volunteer data**. Use a **stricter** threshold for watchlist screening than for owner verification |
| Storage | Embeddings as `float32` BLOB (≈ 2 KB each) |
| 1:N search | NumPy matrix cosine similarity (dummy watchlist is small); FAISS as an optional upgrade |
| Quality gate | Min face size, Laplacian-variance sharpness, brightness range, head-pose limits |

**Alternatives considered**

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| `face_recognition` (dlib) | Very simple API | dlib is hard to build on Windows; less accurate | Fallback only |
| InsightFace (ArcFace, ONNX) | High accuracy; avoids TensorFlow | Slightly more setup | **Recommended fallback** if TensorFlow conflicts appear |
| `facenet-pytorch` | PyTorch-only stack | Smaller ecosystem | Alternative |

**Known risk:** DeepFace depends on TensorFlow/Keras, while YOLOv8 and EasyOCR use PyTorch. They normally coexist, but the install is large and versions can clash. Use a **dedicated virtual environment** and test the full import chain in Phase 0.

### 3.5 Backend: FastAPI

| Item | Decision |
|---|---|
| Framework | **FastAPI** with Uvicorn |
| Why not Flask | FastAPI gives typed request/response models (Pydantic), automatic OpenAPI docs, async support and built-in dependency injection for auth |
| Auth | OAuth2 password flow with JWT access tokens; `passlib[bcrypt]` for hashing |
| Validation | Pydantic v2 models for every endpoint |
| Rate limiting | `slowapi` on public endpoints |
| Structure | Modular monolith: routers → services → repositories |

### 3.6 Database and storage

| Item | Decision |
|---|---|
| Database | **SQLite** in WAL mode (zero setup, single file, enough for the prototype) |
| ORM | SQLAlchemy 2.x with Alembic migrations |
| Evidence files | Local folder `data/evidence/<yyyy>/<mm>/<session_id>/`, accessed only via authenticated API |
| Embeddings | BLOB columns in the owner, `wanted_list` and `missing_reports` tables |
| Upgrade path | PostgreSQL (change the connection string); FAISS for large watchlists |
| Backup | Copy DB file and evidence folder; seed script can rebuild everything |

SQLite was chosen to match the project report and because the demo runs on one machine. It is not suitable for many concurrent writers, which the prototype does not need.

### 3.7 Notifications and alerts

| Channel | Used for | Choice | Notes |
|---|---|---|---|
| **Telegram Bot** | Owner **Allow / Complain** | `python-telegram-bot` (long polling) | Free; inline buttons; sends the driver snapshot; no public URL needed |
| **Email (SMTP)** | Police station alerts | `smtplib` / `fastapi-mail` | Gmail needs an app password (2-step verification on) |
| **SMS** | Optional police/owner SMS | Twilio | Trial accounts send only to **verified numbers**; use for a short demo |
| **Dashboard** | Police operators | Streamlit alerts and review pages | Always available |
| **Simulated mode** | Demo safety | Writes to a mock station inbox table | Default for tests and demo fallback |
| **Push (FCM)** | Not used in prototype | — | Needs a mobile app; listed under future work |

**Why Telegram instead of only SMS or Firebase?** The owner needs **two tap-able actions**. SMS cannot carry buttons without a hosted link, and Firebase push needs a mobile app. A Telegram bot is free, gives buttons and photos immediately, and works with long polling on a laptop. A signed-link web page remains a possible fallback.

### 3.7a Deviation from the project report

| Report mentions | This plan uses | Reason |
|---|---|---|
| Twilio SMS / Firebase for alerts | Telegram (owner), SMTP + dashboard (police), Twilio optional | Free, no mobile app needed, supports Allow/Complain buttons |
| Flask / FastAPI | FastAPI | Typed models and auto-docs |
| HTML-CSS-JS or Streamlit | Streamlit | Fastest route to a working operator dashboard |
| face_recognition / DeepFace | DeepFace (InsightFace fallback) | Easier install; stronger models |

The report can keep its original wording as "options considered".

### 3.8 Dashboard: Streamlit

| Item | Decision |
|---|---|
| Framework | **Streamlit**, multipage app, talks to FastAPI over REST (no direct DB access) |
| Pages | Live feed · Alerts · Review queue · Search · Analytics · Admin · Audit log |
| Charts / maps | Plotly (charts), Folium or `st.map` (alert map) |
| Auto-refresh | Periodic polling of API endpoints |
| Auth | Login page → JWT stored in session state; page access by role |

**Why not React?** A JS front-end adds a second language and build chain. Streamlit is enough for the operator console and keeps the focus on the AI pipeline.

### 3.9 Background jobs

| Job | Purpose |
|---|---|
| Owner-response timeout | Move unanswered cases to review (FR-OWN-05) |
| Outbox retry | Re-send failed alerts with exponential back-off (FR-ALR-04) |
| Retention purge | Delete evidence older than the retention window (FR-ADM-04) |
| Review SLA highlight | Mark overdue review cases (FR-HC-04) |

**APScheduler** runs in-process. Celery/Redis would be overkill for a single-machine prototype.

### 3.10 Testing, quality and DevOps

| Area | Tool |
|---|---|
| Unit / integration tests | `pytest`, `pytest-cov`, `httpx` (API tests) |
| Decision-engine tests | Table-driven tests from the PRD §5 matrix (100% branch coverage) |
| Evaluation | `scikit-learn` (precision/recall, ROC), `matplotlib` / `seaborn` |
| Linting / format | `ruff`, `black`, `mypy` (optional) |
| Hooks | `pre-commit` |
| Security | `pip-audit`, `.env` excluded via `.gitignore` |
| CI (optional) | GitHub Actions: lint + unit tests (models mocked) |
| Replay testing | Recorded video/image sessions fed through the pipeline |

## 4. Hardware and Environment

| Item | Minimum | Recommended |
|---|---|---|
| Laptop/PC | Quad-core CPU, 8 GB RAM | 16 GB RAM, NVIDIA GPU (4 GB+ VRAM) with CUDA |
| Storage | 10 GB free (models, datasets, evidence) | 30 GB SSD |
| Phone | Android 8+, rear camera ≥ 8 MP | 12 MP+, tripod/holder |
| Network | Shared Wi-Fi (2.4/5 GHz) | Wi-Fi 5 GHz or USB tethering |
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
easyocr
pytesseract
deepface
tf-keras
# --- Backend ---
fastapi
uvicorn[standard]
pydantic
pydantic-settings
sqlalchemy
alembic
passlib[bcrypt]
python-jose[cryptography]
python-multipart
slowapi
apscheduler
httpx
# --- Notifications ---
python-telegram-bot
twilio            # optional
# --- Dashboard ---
streamlit
plotly
folium
pandas
# --- Quality / test ---
pytest
pytest-cov
scikit-learn
matplotlib
ruff
black
pre-commit
pip-audit
loguru
```

**System packages:** Tesseract OCR binary (Windows installer or `apt install tesseract-ocr`), CUDA drivers if using a GPU.

## 6. Environment Setup (Reference)

```bash
# 1. Create an isolated environment (Python 3.10 or 3.11)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Smoke-test the whole import chain (Phase 0 exit check)
python -c "import cv2, ultralytics, easyocr, deepface, fastapi, streamlit; print('OK')"

# 4. Configure secrets
cp .env.example .env             # add TELEGRAM_BOT_TOKEN, SMTP_*, JWT_SECRET

# 5. Build the dummy database
python scripts/seed_data.py

# 6. Run services
uvicorn app.main:app --reload     # API
streamlit run dashboard/Home.py   # Dashboard
python -m app.pipeline.run --source http://<phone-ip>:8080/video
```

## 7. Licences and Costs

| Component | Licence (verify before redistribution) | Cost |
|---|---|---|
| Python, FastAPI, SQLAlchemy | PSF / MIT | Free |
| OpenCV | Apache-2.0 | Free |
| Ultralytics YOLOv8 | **AGPL-3.0** | Free for academic use |
| EasyOCR, Tesseract | Apache-2.0 | Free |
| DeepFace | MIT (model weights have their own terms) | Free |
| Streamlit | Apache-2.0 | Free |
| python-telegram-bot | LGPL-3.0 | Free |
| Telegram Bot API | Free service | Free |
| Gmail SMTP | Free personal tier (limits apply) | Free |
| Twilio | Trial credits; verified numbers only | Free trial |
| Google Colab / Kaggle | Free tier with GPU quotas | Free |

Face datasets and plate datasets each carry their own licence; record the source and licence of every dataset in `docs/datasets.md`.

## 8. Technology Risks and Fallbacks

| Risk | Fallback |
|---|---|
| TensorFlow/PyTorch conflict | Switch face module to InsightFace (ONNX Runtime) behind the same `FaceService` interface |
| EasyOCR slow on CPU | Use Tesseract for the first pass; or run OCR only on the best 3 frames |
| Phone stream unstable | USB tethering; laptop webcam; recorded video replay |
| YOLO plate model weak on Indian plates | Add more own images; increase augmentation; use `yolov8s` |
| Twilio / SMTP limits | Simulated mode and Telegram |
| GPU unavailable | `yolov8n`, lower resolution, process fewer frames per second |

## 9. Revision History

| Version | Date | Change |
|---|---|---|
| 1.0 | 04 Oct 2026 | Initial stack selection |
