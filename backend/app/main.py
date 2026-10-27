"""ForestWatch API.

POST   /jobs                  enqueue a processing job (returns immediately)
GET    /jobs, /jobs/{id}      status and summary
GET    /change-events         GeoJSON FeatureCollection (filters: job_id, bbox, min_confidence, status)
PATCH  /change-events/{id}    confirm / reject a candidate (human review)
GET    /stats                 counts by status and total area
GET    /health
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import Base, engine, get_db
from .models import ChangeEvent, Job, utcnow
from .schemas import EventUpdate, JobCreate, JobOut

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables:          # tests / quick local dev; production uses Alembic
        Base.metadata.create_all(engine)
    yield


app = FastAPI(title="ForestWatch API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", response_model=JobOut, status_code=202)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    job = Job(method=body.method, params={"seasonal": body.seasonal}, status="queued")
    db.add(job); db.commit(); db.refresh(job)
    if settings.sync_jobs:
        from .worker import process_job
        process_job(job.id)
        db.refresh(job)
        return job
    try:
        from redis import Redis
        from rq import Queue
        Queue("forestwatch", connection=Redis.from_url(settings.redis_url)).enqueue(
            "app.worker.process_job", job.id, job_timeout=3600)
    except Exception as exc:
        job.status, job.error, job.finished_at = "failed", f"Queue unavailable: {exc}"[:500], utcnow()
        db.commit()
        raise HTTPException(status_code=503, detail="Job queue unavailable")
    return job


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return db.scalars(select(Job).order_by(Job.id.desc()).limit(limit)).all()


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return job


def _parse_bbox(bbox: str):
    try:
        lon0, lat0, lon1, lat1 = (float(v) for v in bbox.split(","))
    except ValueError:
        raise HTTPException(422, "bbox must be 'min_lon,min_lat,max_lon,max_lat'")
    return lon0, lat0, lon1, lat1


@app.get("/change-events")
def list_events(job_id: int | None = None, bbox: str | None = None,
                min_confidence: float = Query(0.0, ge=0, le=1), status: str | None = None,
                limit: int = Query(5000, ge=1, le=20000), db: Session = Depends(get_db)):
    if job_id is None:       # default: the latest completed job
        job_id = db.scalar(select(func.max(Job.id)).where(Job.status == "completed"))
        if job_id is None:
            return {"type": "FeatureCollection", "features": []}
    q = select(ChangeEvent).where(ChangeEvent.job_id == job_id)
    if bbox:
        lon0, lat0, lon1, lat1 = _parse_bbox(bbox)
        q = q.where(ChangeEvent.max_lon >= lon0, ChangeEvent.min_lon <= lon1,
                    ChangeEvent.max_lat >= lat0, ChangeEvent.min_lat <= lat1)
    if min_confidence > 0:
        q = q.where(or_(ChangeEvent.confidence.is_(None), ChangeEvent.confidence >= min_confidence))
    if status:
        q = q.where(ChangeEvent.status == status)
    events = db.scalars(q.order_by(ChangeEvent.id).limit(limit)).all()
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": e.id, "geometry": e.geometry,
         "properties": {"id": e.id, "job_id": e.job_id, "status": e.status, "area_ha": e.area_ha,
                        "n_pixels": e.n_pixels, "confidence": e.confidence, "note": e.note}}
        for e in events]}


@app.patch("/change-events/{event_id}")
def review_event(event_id: int, body: EventUpdate, db: Session = Depends(get_db)):
    ev = db.get(ChangeEvent, event_id)
    if ev is None:
        raise HTTPException(404, "Event not found")
    ev.status, ev.note, ev.reviewed_at = body.status, body.note, utcnow()
    db.commit()
    return {"id": ev.id, "status": ev.status, "note": ev.note}


@app.get("/stats")
def stats(job_id: int | None = None, db: Session = Depends(get_db)):
    if job_id is None:
        job_id = db.scalar(select(func.max(Job.id)).where(Job.status == "completed"))
    rows = db.execute(select(ChangeEvent.status, func.count(), func.coalesce(func.sum(ChangeEvent.area_ha), 0.0))
                      .where(ChangeEvent.job_id == job_id).group_by(ChangeEvent.status)).all() if job_id else []
    by = {s: {"count": c, "area_ha": float(a)} for s, c, a in rows}
    return {"job_id": job_id, "by_status": by,
            "total_events": sum(v["count"] for v in by.values()),
            "total_area_ha": sum(v["area_ha"] for v in by.values())}
