"""API integration test (needs fastapi, httpx, sqlalchemy). Skipped when they are missing.
Runs the whole path: fake stacks -> POST /jobs (inline) -> events -> review -> stats."""
import os
import sys
import tempfile
from pathlib import Path
import pytest

pytest.importorskip("fastapi"); pytest.importorskip("httpx"); pytest.importorskip("sqlalchemy")

ROOT = Path(__file__).resolve().parents[1]
TMP = tempfile.mkdtemp()
os.environ.update({"ROOT_DIR": TMP, "DATABASE_URL": f"sqlite:///{TMP}/test.db", "SYNC_JOBS": "1",
                   "AUTO_CREATE_TABLES": "1", "CONFIG_PATH": str(ROOT / "configs" / "aravalli.yaml")})
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))

import numpy as np                                    # noqa: E402
import yaml                                           # noqa: E402
from fastapi.testclient import TestClient             # noqa: E402
from forestwatch.synthetic import make_scene_pair     # noqa: E402
from test_phase2 import _write_fake_stacks            # noqa: E402


@pytest.fixture(scope="module")
def client():
    cfg = yaml.safe_load((ROOT / "configs" / "aravalli.yaml").read_text())
    cfg["region"]["output_crs"] = "EPSG:32643"        # skip reprojection (pyproj not required)
    cfg_path = Path(TMP) / "cfg.yaml"; cfg_path.write_text(yaml.safe_dump(cfg))
    os.environ["CONFIG_PATH"] = str(cfg_path)
    _write_fake_stacks(TMP, make_scene_pair(256, 256, seed=3, season_dip=0.0, cloud_blobs=2))
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_job_lifecycle_and_review(client):
    r = client.post("/jobs", json={"method": "baseline", "seasonal": True})
    assert r.status_code == 202 and r.json()["status"] == "completed", r.text
    job = r.json(); assert job["n_events"] > 0
    fc = client.get("/change-events").json()
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == job["n_events"]
    eid = fc["features"][0]["id"]
    assert client.patch(f"/change-events/{eid}", json={"status": "confirmed", "note": "visible clearing"}).status_code == 200
    assert len(client.get("/change-events", params={"status": "confirmed"}).json()["features"]) == 1
    s = client.get("/stats").json()
    assert s["total_events"] == job["n_events"] and s["by_status"]["confirmed"]["count"] == 1
    assert client.get("/change-events", params={"bbox": "0,0,1,1"}).json()["features"] == []
    assert client.get("/change-events", params={"bbox": "bad"}).status_code == 422


def test_failed_job_records_error(client):
    r = client.post("/jobs", json={"method": "unet", "seasonal": False})      # no model file exists
    assert r.status_code == 202
    j = client.get(f"/jobs/{r.json()['id']}").json()
    assert j["status"] == "failed" and "model" in j["error"].lower()
