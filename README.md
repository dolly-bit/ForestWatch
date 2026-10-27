# ForestWatch

Satellite-based **vegetation-loss monitoring** for the Aravalli range (Delhi NCR). Free Sentinel-2 imagery
-> cloud-masked same-season composites -> NDVI baseline and a bi-temporal U-Net -> seasonal-persistence filter
-> candidate clearing polygons -> API + database -> interactive map with human review.

> Candidates are produced by an algorithm and need visual / field verification. Not an enforcement,
> legal or official forest-accounting tool. Results depend on your labels, region and dates.

## Architecture
    STAC search -> common 10 m grid -> cloud mask (SCL) -> median composites (before / after windows)
        -> [NDVI baseline | U-Net on 13-channel before/after/diff features]
        -> seasonal persistence filter -> small-blob removal -> polygons (GeoJSON, EPSG:4326)
    Next.js + MapLibre  <->  FastAPI  <->  PostgreSQL (Alembic)      jobs: Redis + RQ worker

## Layout
    configs/aravalli.yaml        all thresholds, windows, split, model settings
    src/forestwatch/             data/ preprocess/ change/ models/ eval/ labels/ pipeline.py synthetic.py
    scripts/                     demo_synthetic, search_scenes, build_stacks, make_labels,
                                 run_baseline, train_unet, evaluate, predict
    backend/app/                 FastAPI (main), SQLAlchemy models, RQ worker;  backend/alembic/ migrations
    frontend/                    Next.js (app router) + MapLibre
    tests/                       test_phase1, test_phase2 (numpy) | test_torch, test_api (skipped if deps missing)
    docker-compose.yml  Dockerfile.api  Makefile  .github/workflows/ci.yml

## 1. Install and verify (offline, ~10 min)
    python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
    pip install -e ".[dev]"
    pytest                                  # 20 pass (torch/api tests skip until you install those extras)
    python scripts/demo_synthetic.py        # writes outputs/phase1_demo.png

## 2. Real data
    pip install -e ".[geo]"
    # edit configs/aravalli.yaml: bbox + the two same-season date windows (check in QGIS first)
    python scripts/search_scenes.py         # catalogs -> data/raw/
    python scripts/build_stacks.py          # stacks -> data/stacks/{before,after}/   (test on ONE scene first)
    python scripts/run_baseline.py          # baseline change map (+ scores if labels exist)
    # label in QGIS (polygons of clear vegetation -> cleared land), export GeoJSON, then:
    python scripts/make_labels.py data/labels/my_polygons.geojson
    python scripts/evaluate.py              # frozen TEST blocks: baseline +/- seasonal filter (+ U-Net)

## 3. Train the U-Net (needs labels)
    pip install -e ".[ml]"                  # torch; use a GPU or free Colab/Kaggle for speed
    python scripts/train_unet.py            # saves models/unet_change.pt + learning-curve CSV
    python scripts/evaluate.py              # now includes U-Net rows
    python scripts/predict.py --method unet # outputs/change_events.geojson

## 4. Backend + map
Quick local run, no Docker/Redis (jobs run inline):
    pip install -e ".[api]"
    export SYNC_JOBS=1 AUTO_CREATE_TABLES=1          # Windows: set VAR=1
    cd backend && uvicorn app.main:app --reload --port 8000     # docs at http://localhost:8000/docs
    cd frontend && cp .env.local.example .env.local && npm install && npm run dev   # http://localhost:3000

Full stack (Postgres + Redis + worker + web):
    docker compose up --build               # api runs `alembic upgrade head` on start
    # U-Net inside Docker needs torch:  docker compose build --build-arg INSTALL_TORCH=1 api worker
    # Needs data/stacks/{before,after}/*.npz on the host first.

## Method notes
- Same-season windows (e.g. Oct-Dec of two years) avoid dry-season leaf-drop false alarms.
- Split: contiguous groups of blocks (+ buffer) per train/val/test. Scattered random blocks plus a buffer
  left almost no training data (see tests/test_phase2.py).
- Baseline "confidence" is a heuristic NDVI-drop score; U-Net confidence is the mean model probability.
  Neither is a calibrated probability.
- Polygons ignore interior holes; contours follow pixel edges approximately (areas use pixel counts).

## Status: what has and has not been run
| Part | Status |
|---|---|
| Masking, composites, splits, baseline, seasonal filter, vectorizer, tiling, metrics, label rasteriser, end-to-end pipeline on synthetic stacks | Unit/integration tested (20 tests) |
| STAC search, scene download/reprojection (rasterio) | Written, NOT run (needs network) |
| U-Net, training loop, checkpoint loading | Written, NOT run (torch not installed where this was built); `tests/test_torch.py` will check it |
| FastAPI, SQLAlchemy, worker, Alembic migration | Written, NOT run; `tests/test_api.py` will check API + worker once deps are installed |
| Docker Compose, Dockerfile, Next.js frontend | Written, NOT built or run |
Run `pytest` after `pip install -e ".[dev,api,ml]"` to exercise the untested Python parts. Expect to fix small
issues on the first real run: paste errors and iterate.

## Verify before relying on
STAC catalog URL and asset names (red/nir/swir22/scl), the 2022 reflectance offset, data licences and terms,
OSM tile usage policy for the basemap (use a proper tile provider if you deploy), package versions in
frontend/package.json.

## Next steps
Before/after image slider, PostGIS geometry column, Sentinel-1 fusion (optional), model calibration,
comparison against public alert products, spatial cross-validation across more regions.
