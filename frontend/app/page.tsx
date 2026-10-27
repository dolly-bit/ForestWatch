"use client";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createJob, getEvents, getJobs, getStats, reviewEvent,
  type EventCollection, type EventStatus, type Job, type Stats,
} from "@/lib/api";
import ReviewPanel from "@/components/ReviewPanel";

// MapLibre needs the browser, so skip server-side rendering for the map.
const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

const EMPTY: EventCollection = { type: "FeatureCollection", features: [] };

export default function Home() {
  const [events, setEvents] = useState<EventCollection>(EMPTY);
  const [stats, setStats] = useState<Stats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [minConf, setMinConf] = useState(0);
  const [status, setStatus] = useState("");
  const [method, setMethod] = useState<"baseline" | "unet">("baseline");
  const [seasonal, setSeasonal] = useState(true);
  const [fitKey, setFitKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [launching, setLaunching] = useState(false);

  const refresh = useCallback(async (refit = false) => {
    try {
      const [ev, st, js] = await Promise.all([getEvents(minConf, status), getStats(), getJobs()]);
      setEvents(ev); setStats(st); setJobs(js); setError(null);
      if (refit) setFitKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [minConf, status]);

  useEffect(() => { refresh(true); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { refresh(false); }, [minConf, status, refresh]);

  // poll while a job is queued or running
  const active = jobs.some((j) => j.status === "queued" || j.status === "running");
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => refresh(true), 3000);
    return () => clearInterval(t);
  }, [active, refresh]);

  const launch = async () => {
    setLaunching(true);
    try { await createJob(method, seasonal); await refresh(true); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLaunching(false); }
  };

  const onReview = async (id: number, st: EventStatus, note: string) => {
    await reviewEvent(id, st, note);
    await refresh(false);
  };

  const selectedFeature = useMemo(
    () => events.features.find((f) => f.properties.id === selected) ?? null, [events, selected]);

  return (
    <div className="app">
      <aside className="side">
        <div>
          <h1>ForestWatch</h1>
          <p className="muted">Candidate vegetation-loss areas from Sentinel-2 change detection (study region: Aravallis, Delhi NCR).</p>
        </div>

        <section className="card">
          <h2>Run detection</h2>
          <label>Method</label>
          <select value={method} onChange={(e) => setMethod(e.target.value as "baseline" | "unet")}>
            <option value="baseline">NDVI baseline</option>
            <option value="unet">U-Net (needs trained model)</option>
          </select>
          <div className="row" style={{ margin: "8px 0" }}>
            <input type="checkbox" checked={seasonal} onChange={(e) => setSeasonal(e.target.checked)} id="seas" />
            <label htmlFor="seas">Seasonal persistence filter</label>
          </div>
          <button className="primary" disabled={launching || active} onClick={launch}>
            {active ? "Job running..." : "Start job"}
          </button>
          {jobs[0] && (
            <p className="muted">
              Latest: #{jobs[0].id} <span className="badge">{jobs[0].status}</span> {jobs[0].method}
              {jobs[0].status === "completed" && ` | ${jobs[0].n_events} areas, ${jobs[0].total_area_ha.toFixed(1)} ha`}
            </p>
          )}
          {jobs[0]?.error && <p className="err">{jobs[0].error}</p>}
        </section>

        <section className="card">
          <h2>Filters</h2>
          <label>Minimum confidence: {minConf.toFixed(2)}</label>
          <input type="range" min={0} max={1} step={0.05} value={minConf}
                 onChange={(e) => setMinConf(Number(e.target.value))} style={{ width: "100%" }} />
          <label>Status</label>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="candidate">Candidate</option>
            <option value="confirmed">Confirmed</option>
            <option value="rejected">Rejected</option>
          </select>
        </section>

        <section className="card">
          <h2>Summary</h2>
          {stats && stats.total_events > 0 ? (
            <>
              {Object.entries(stats.by_status).map(([k, v]) => (
                <div className="stat" key={k}><span>{k}</span><b>{v.count} ({v.area_ha.toFixed(1)} ha)</b></div>
              ))}
              <div className="stat"><span>Total</span><b>{stats.total_events} ({stats.total_area_ha.toFixed(1)} ha)</b></div>
            </>
          ) : <p className="muted">No results yet. Start a job.</p>}
          <div className="legend" style={{ marginTop: 8 }}>
            <span><i className="dot" style={{ background: "#facc15" }} />low conf.</span>
            <span><i className="dot" style={{ background: "#dc2626" }} />high conf.</span>
            <span><i className="dot" style={{ background: "#16a34a" }} />confirmed</span>
            <span><i className="dot" style={{ background: "#6b7280" }} />rejected</span>
          </div>
        </section>

        <section className="card">
          <h2>Review</h2>
          <ReviewPanel feature={selectedFeature} onReview={onReview} />
        </section>

        {error && <p className="err">API error: {error}</p>}
      </aside>
      <main className="map">
        <MapView data={events} selectedId={selected} onSelect={setSelected} fitKey={fitKey} />
      </main>
    </div>
  );
}
