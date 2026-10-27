"""Tables. Kept to two on purpose: jobs (processing runs) and change_events (flagged polygons).

Geometry is stored as GeoJSON (JSON) plus indexed bounding-box columns, which works on
Postgres and SQLite. Upgrading to a PostGIS geometry column is a clean next step
(add a migration, GeoAlchemy2, and ST_Intersects for the bbox filter).
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)   # queued|running|completed|failed
    method: Mapped[str] = mapped_column(String(16))                                  # baseline|unet
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    n_events: Mapped[int] = mapped_column(Integer, default=0)
    total_area_ha: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    events: Mapped[list["ChangeEvent"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class ChangeEvent(Base):
    __tablename__ = "change_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    geometry: Mapped[dict] = mapped_column(JSON)                  # GeoJSON Polygon, EPSG:4326
    min_lon: Mapped[float] = mapped_column(Float)
    min_lat: Mapped[float] = mapped_column(Float)
    max_lon: Mapped[float] = mapped_column(Float)
    max_lat: Mapped[float] = mapped_column(Float)
    area_ha: Mapped[float] = mapped_column(Float)
    n_pixels: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="candidate", index=True)  # candidate|confirmed|rejected
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    job: Mapped[Job] = relationship(back_populates="events")

    __table_args__ = (Index("ix_change_events_bbox", "min_lon", "min_lat", "max_lon", "max_lat"),)
