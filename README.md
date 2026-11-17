# VehiGuard

**AI-powered stolen and cloned vehicle detection network** (final-year engineering project, proof of concept)

VehiGuard reads vehicle number plates from phone-camera feeds at several camera locations and matches them against stolen and missing vehicle records. Every accepted plate is recorded as a **sighting**. Sightings from different locations are compared to find **suspected cloned plates**: physically impossible journeys and appearance differences. The system collects time- and location-stamped evidence, alerts police users, and tracks each case until the vehicle is recovered.

> The prototype uses phone cameras and a **manually created dummy database** only. It performs **no face recognition** and uses no real stolen-vehicle data.

## Project status

The project is in **Phase 0: re-baseline and environment**. The project was renamed from VehiLence to VehiGuard, and the plan was rewritten. Early test scripts for plate detection and OCR are working. See [docs/phase_definition.md](docs/phase_definition.md) for the full plan.

## Tech stack

| Layer | Choice |
|---|---|
| Capture | Phone camera apps (DroidCam / Iriun / IP Webcam) + OpenCV |
| Detection | YOLOv8 (Ultralytics) |
| OCR | PaddleOCR (primary), EasyOCR (fallback) |
| Backend | FastAPI + Uvicorn + Pydantic |
| Database | PostgreSQL + SQLAlchemy 2.x + Alembic |
| Dashboard | React (Vite) + Leaflet + Recharts |
| Quality | pytest, ruff, black, pre-commit |

Details and reasons for each choice: [docs/tech_stack.md](docs/tech_stack.md).

## Repository layout

```
app/          Backend: domain logic, pipeline, database, notifiers, API
config/       settings.yaml, plate_patterns.yaml
dashboard/    Old Streamlit console (to be replaced)
dashboard-web/ React dashboard (Vite)
data/         Local test images, crops and database (not committed)
docs/         Project documents
scripts/      Setup, seed and experiment scripts
tests/        Unit, integration and scenario tests
```

## Setup (Windows)

These steps need Python 3.10 or 3.11.

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pre-commit install
copy .env.example .env
```

Then set your PostgreSQL password in `DATABASE_URL` in `.env`, and check the connection:

```bat
python -m scripts.check_db
```

Create the tables (run this again after pulling new migrations), then run the tests:

```bat
alembic upgrade head
pytest
```

To rebuild the dummy database (this **empties every table** first), run:

```bat
python scripts/seed_data.py
```

It creates 3 police stations, 3 cameras, 25 vehicles, 6 stolen/missing reports and 4 demo users (`admin`, `officer`, `operator`, `viewer`). Their password comes from `SEED_USER_PASSWORD` in `.env`. If that is empty, a random password is printed once.

## Running the app

Use two terminals, both started in the project folder.

```bat
:: Terminal 1: backend API on http://127.0.0.1:8000
uvicorn app.main:app --reload

:: Terminal 2: React dashboard on http://localhost:5173
cd dashboard-web
npm install
npm run dev
```

The dashboard sends `/api` requests to the backend, so open http://localhost:5173. The status page shows **API: OK** and **Database: OK** when both are running.

## Plate recognition pipeline

The pipeline reads a camera, finds vehicles and plates, reads each plate with OCR (PaddleOCR first, then EasyOCR), checks it against the Indian plate rules, and votes over several frames. Each vehicle it finishes with becomes a **sighting** stored with evidence images in `data/evidence/`.

```bat
:: Live phone camera registered in the database (CAM-A)
python -m app.pipeline.run --camera CAM-A

:: Any source: a phone address, a webcam (0), a video file or an image folder (replay)
python -m app.pipeline.run --camera CAM-B --source data\test_sessions\cam_b.mp4

:: Try it without writing to the database
python -m app.pipeline.run --camera TEST --source data\test_plates --no-db

:: Two cameras at once
python -m app.pipeline.run --camera CAM-A --camera CAM-B
```

A preview window shows the vehicle boxes, plate boxes and plate text. Press **q** to stop. Thresholds and model choices are set in `config/settings.yaml`.

## Measuring accuracy

Put plate photos in `data/test_plates/`. To score OCR, name each file after its plate number, for example `KA19AB1234.jpg`.

```bat
python scripts\evaluate.py        :: detection and OCR accuracy, saved to docs\results\
python scripts\compare_ocr.py     :: PaddleOCR vs EasyOCR, with and without preprocessing
python scripts\detect_plates.py   :: save plate crops to data\plate_crops\ (used by compare_ocr)
```

To train a better plate detector on a free Colab GPU, follow [docs/plate_dataset_guide.md](docs/plate_dataset_guide.md).

## Documentation

| Document | Contents |
|---|---|
| [problem_statement.md](docs/problem_statement.md) | Background, problem, objectives and scope |
| [prd.md](docs/prd.md) | Functional and non-functional requirements, decision matrix |
| [architecture.md](docs/architecture.md) | Components, data model, clone-detection rule |
| [tech_stack.md](docs/tech_stack.md) | Technology choices and full setup guide |
| [phase_definition.md](docs/phase_definition.md) | Delivery plan by phase |
| [datasets.md](docs/datasets.md) | Dataset and model log |
| [consent_form.md](docs/consent_form.md) | Volunteer consent form |

## Ethics and privacy

All real vehicles and plates used in testing are recorded with the owner's consent, as set out in [docs/consent_form.md](docs/consent_form.md). Owner and case records are fictional. Data in `data/` stays local and is not committed.

## Author

Vinisha Marina Dsouza
