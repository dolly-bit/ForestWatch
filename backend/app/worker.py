"""Background job: run the pipeline and store the resulting polygons.

RQ imports this as `app.worker.process_job`. Errors are recorded on the job row.
"""
from __future__ import annotations
import logging
import traceback
from .config import get_settings
from .db import SessionLocal
from .models import ChangeEvent, Job, utcnow

log = logging.getLogger("forestwatch.worker")


def process_job(job_id: int) -> None:
    from forestwatch.config import load_config
    from forestwatch.pipeline import run_pipeline
    from forestwatch.change.vectorize import feature_bbox

    s = get_settings()
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None or job.status in ("running", "completed"):
            return                                     # idempotent: duplicate delivery is a no-op
        job.status, job.started_at = "running", utcnow()
        db.commit()

        cfg = load_config(s.config_path)
        res = run_pipeline(cfg, s.root_dir, method=job.method,
                           seasonal=job.params.get("seasonal"), checkpoint=s.model_path)
        total = 0.0
        for ft in res["features"]:
            lon0, lat0, lon1, lat1 = feature_bbox(ft)
            p = ft["properties"]
            db.add(ChangeEvent(job_id=job.id, geometry=ft["geometry"], min_lon=lon0, min_lat=lat0,
                               max_lon=lon1, max_lat=lat1, area_ha=p["area_ha"], n_pixels=p["n_pixels"],
                               confidence=p["confidence"]))
            total += p["area_ha"]
        job.status, job.n_events, job.total_area_ha, job.finished_at = "completed", len(res["features"]), total, utcnow()
        db.commit()
    except Exception as exc:                           # record the failure instead of losing it
        log.error("job %s failed\n%s", job_id, traceback.format_exc())
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            job.status, job.error, job.finished_at = "failed", f"{type(exc).__name__}: {exc}"[:2000], utcnow()
            db.commit()
    finally:
        db.close()
