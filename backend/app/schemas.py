from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    method: Literal["baseline", "unet"] = "baseline"
    seasonal: bool = True


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    method: str
    params: dict
    error: Optional[str] = None
    n_events: int
    total_area_ha: float
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class EventUpdate(BaseModel):
    status: Literal["candidate", "confirmed", "rejected"]
    note: Optional[str] = Field(default=None, max_length=1000)
