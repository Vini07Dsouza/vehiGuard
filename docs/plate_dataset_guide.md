# Plate Dataset Guide — VehiGuard (tasks 2.3 and 2.4)

This guide explains how to build the labelled plate dataset, train the plate detector on Colab, and measure it. The current detector was trained on Nepal plates and misses some Indian plates. The Phase 2 targets are **≥ 90% detection recall** and **≥ 85% OCR exact match** on a held-out test set of **at least 100 images**.

## 1. Collect images

| Set | How many | Source | Used for |
|---|---|---|---|
| Training and validation | 300–1000 | Public Indian plate datasets (Roboflow Universe, Kaggle) plus your own photos | Training |
| **Held-out test** | **≥ 100** | Mostly your own photos (different vehicles, light, angles) | Evaluation only, **never trained on** |

**Rules**

- Log every public dataset in [datasets.md](datasets.md): name, link, licence and date.
- Real plates in your own photos need the owner's signed [consent form](consent_form.md).
- Include hard cases: night, rain, tilted plates, two-line plates, motorcycles, dirty plates, HSRP plates with the blue "IND" strip, and BH-series plates.
- Never put the same vehicle photo in both the training set and the test set.

## 2. Label in Roboflow (free plan)

1. Create an account at roboflow.com and start a project: **Object Detection**, called `indian-plates`.
2. Upload the **training** images. For a public Roboflow Universe set, use **Fork** or **Clone** to copy it into your project.
3. Draw one box per plate, tight around the plate, with the class name `plate`.
4. **Generate** a version:
   - Split: 80% train, 20% valid. Test is 0% here, because the test set is kept outside Roboflow.
   - Preprocessing: Auto-Orient, Resize 640×640 (stretch).
   - Augmentation (×3): Brightness ±25%, Blur up to 1.5 px, Rotation ±10°, Noise up to 2%.
5. Note the **workspace**, **project** and **version** number for the notebook.

**Held-out test set:** label it in a **separate** Roboflow project, then export it in **YOLOv8** format. Put it in the project like this:

```
data/plate_test/
├── KA19AB1234.jpg          name each photo after its plate, if known
├── KA20EF2468_2.jpg        (add _2, _3 ... for more photos of the same plate)
├── unknown_001.jpg         a photo whose plate number you do not know
└── labels/
    ├── KA19AB1234.txt      YOLO labels exported from Roboflow (same file name)
    └── ...
```

The file names give the expected plate for OCR scoring. The labels give the boxes for detection scoring. The `data/` folder is not committed to Git.

## 3. Train on Colab (task 2.4)

1. Open [colab.research.google.com](https://colab.research.google.com), choose **File → Upload notebook**, and select `scripts/train_plate_detector.ipynb`.
2. Choose **Runtime → Change runtime type → T4 GPU**.
3. In the dataset cell, fill in the workspace, project and version. Then choose **Runtime → Run all**, and paste your Roboflow API key when asked.
4. Training takes about 20–40 minutes. At the end, `best.pt` downloads automatically.
5. Rename the file to `plate_detector.pt` and put it in `models/`. Model files are not committed to Git.

## 4. Measure and switch (task 2.10)

Measure both detectors on the same test set:

```bat
python scripts/evaluate.py --name baseline
python scripts/evaluate.py --weights models/plate_detector.pt --name finetuned
```

The results are saved to `docs/results/plate_evaluation_baseline.md` and `..._finetuned.md`, ready for the report. If the fine-tuned model scores better, set this in `config/settings.yaml`:

```yaml
detection:
  plate_model: models/plate_detector.pt
```

Then log the model in [datasets.md](datasets.md).
