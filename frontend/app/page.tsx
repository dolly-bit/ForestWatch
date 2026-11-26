"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createJob, getEvents, getJobs, getStats, reviewEvent,
  type EventCollection, type EventStatus, type Job, type Stats,
} from "@/lib/api";
import ReviewPanel from "@/components/ReviewPanel";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });
const EMPTY: EventCollection = { type: "FeatureCollection", features: [] };

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(value);
}

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

  useEffect(() => { refresh(true); }, []);
  useEffect(() => { refresh(false); }, [minConf, status, refresh]);

  const active = jobs.some((j) => j.status === "queued" || j.status === "running");
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => refresh(true), 3000);
    return () => clearInterval(timer);
  }, [active, refresh]);

  const launch = async () => {
    setLaunching(true);
    try { await createJob(method, seasonal); await refresh(true); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLaunching(false); }
  };

  const onReview = async (id: number, nextStatus: EventStatus, note: string) => {
    await reviewEvent(id, nextStatus, note);
    await refresh(false);
  };

  const selectedFeature = useMemo(
    () => events.features.find((feature) => feature.properties.id === selected) ?? null,
    [events, selected],
  );
  const latest = jobs[0];
  const candidateCount = stats?.total_events ?? events.features.length;
  const candidateArea = stats?.total_area_ha ?? 0;
  const candidateStatus = stats?.by_status?.candidate;
  const completedJobs = jobs.filter((job) => job.status === "completed").length;

  return (
    <main className="site-shell">
      <header className="topbar">
        <a className="brand" href="#overview" aria-label="ForestWatch home">
          <span className="brand-mark">F</span>
          <span>Forest<span className="brand-light">Watch</span></span>
        </a>
        <nav className="main-nav" aria-label="Main navigation">
          <a href="#overview">Overview</a>
          <a href="#workspace">Explore detections</a>
          <a href="#method">Methodology</a>
          <a href="#interpretation">How to read results</a>
        </nav>
        <a className="nav-cta" href="#workspace">Open workspace <span>↗</span></a>
      </header>

      <section className="hero" id="overview">
        <div className="hero-copy">
          <div className="eyebrow"><span className="live-dot" /> EARTH OBSERVATION · DELHI NCR</div>
          <h1>See the changes.<br /><em>Understand the landscape.</em></h1>
          <p className="hero-description">
            ForestWatch uses multi-temporal Sentinel-2 observations to flag potential vegetation-loss
            areas across the Aravalli study region. Explore candidate changes, inspect their locations
            and review detections instead of treating every signal as confirmed loss.
          </p>
          <div className="hero-actions">
            <a className="button button-primary" href="#workspace">Explore detected areas <span>↓</span></a>
            <a className="text-link" href="#method">How detection works <span>→</span></a>
          </div>
          <div className="hero-footnote"><span className="footnote-icon">◎</span> Research prototype · Candidate detections require independent verification</div>
        </div>
        <div className="hero-visual" aria-label="Satellite-inspired landscape illustration">
          <div className="visual-grid" />
          <div className="visual-orbit orbit-one" />
          <div className="visual-orbit orbit-two" />
          <div className="visual-scan scan-one" />
          <div className="visual-caption"><span>STUDY AREA</span><strong>Aravalli Range</strong><small>Delhi National Capital Region, India</small></div>
          <div className="visual-coordinate">28.42° N&nbsp; 77.18° E</div>
          <div className="visual-tag"><span className="live-dot" /> CHANGE MONITORING</div>
        </div>
      </section>

      <section className="metrics-strip" aria-label="Latest detection summary">
        <div className="metric-intro"><span className="section-kicker">CURRENT RUN</span><strong>Detection snapshot</strong><small>Live values from the ForestWatch API</small></div>
        <div className="metric"><span>Candidate polygons</span><strong>{formatNumber(candidateCount)}</strong><small>Flagged areas for review</small></div>
        <div className="metric"><span>Candidate area</span><strong>{formatNumber(candidateArea)} <i>ha</i></strong><small>Not verified vegetation loss</small></div>
        <div className="metric"><span>Completed jobs</span><strong>{completedJobs}</strong><small>Recent jobs in this database</small></div>
        <div className="metric metric-status"><span>Latest job</span><strong className="status-value">{latest?.status ?? "No runs"}</strong><small>{latest ? `#${latest.id} · ${latest.method}` : "Run a detection to begin"}</small></div>
      </section>

      <section className="workspace-section" id="workspace">
        <div className="section-heading">
          <div><span className="section-kicker">INTERACTIVE EXPLORER</span><h2>Explore candidate changes</h2></div>
          <p>Every outlined feature is an algorithmically flagged location. Select a polygon to inspect its attributes and record a review decision.</p>
        </div>
        <div className="workspace-grid">
          <aside className="control-column">
            <section className="panel-card run-card">
              <div className="panel-heading"><span className="panel-icon">⌁</span><div><h3>Run detection</h3><p>Configure a new analysis job</p></div></div>
              <label htmlFor="method">Detection method</label>
              <select id="method" value={method} onChange={(e) => setMethod(e.target.value as "baseline" | "unet")}>
                <option value="baseline">NDVI baseline</option>
                <option value="unet">U-Net (requires trained model)</option>
              </select>
              <label className="check-row"><input type="checkbox" checked={seasonal} onChange={(e) => setSeasonal(e.target.checked)} /> <span>Seasonal persistence filter</span></label>
              <button className="button button-run" disabled={launching || active} onClick={launch}>
                {active ? "Processing job…" : launching ? "Starting…" : "Start detection"} <span>→</span>
              </button>
              {latest && <div className="job-state"><span className={`state-dot state-${latest.status}`} /> Latest job #{latest.id}: <b>{latest.status}</b>{latest.error && <p className="error-text">{latest.error}</p>}</div>}
            </section>

            <section className="panel-card filter-card">
              <div className="panel-heading"><span className="panel-icon">⌕</span><div><h3>Filter detections</h3><p>Refine the map view</p></div></div>
              <div className="filter-label"><label htmlFor="confidence">Minimum confidence</label><strong>{minConf.toFixed(2)}</strong></div>
              <input id="confidence" className="confidence-slider" type="range" min={0} max={1} step={0.05} value={minConf} onChange={(e) => setMinConf(Number(e.target.value))} />
              <label htmlFor="status">Review status</label>
              <select id="status" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All statuses</option><option value="candidate">Candidate</option><option value="confirmed">Confirmed</option><option value="rejected">Rejected</option>
              </select>
              <div className="map-legend">
                <span><i className="legend-swatch low" /> Lower score</span><span><i className="legend-swatch high" /> Higher score</span>
                <span><i className="legend-swatch confirmed" /> Confirmed</span><span><i className="legend-swatch rejected" /> Rejected</span>
              </div>
            </section>

            <section className="panel-card review-card">
              <div className="panel-heading"><span className="panel-icon">＋</span><div><h3>Inspect a detection</h3><p>{selectedFeature ? `Feature #${selectedFeature.properties.id}` : "Select a polygon on the map"}</p></div></div>
              <ReviewPanel feature={selectedFeature} onReview={onReview} />
            </section>
            {error && <div className="api-error">API connection: {error}</div>}
          </aside>

          <div className="map-column">
            <div className="map-toolbar"><div><span className="map-live-dot" /> <strong>Aravalli study region</strong><span className="map-subtitle">· Candidate change locations</span></div><span className="map-count">{events.features.length.toLocaleString("en-IN")} features shown</span></div>
            <div className="map-frame"><MapView data={events} selectedId={selected} onSelect={setSelected} fitKey={fitKey} /></div>
            <div className="map-foot"><span>Map data © OpenStreetMap contributors</span><span>Click a polygon to inspect · Use map controls to zoom</span></div>
          </div>
        </div>
      </section>

      <section className="method-section" id="method">
        <div className="section-heading">
          <div><span className="section-kicker">THE APPROACH</span><h2>From satellite observations to candidate areas</h2></div>
          <p>A transparent baseline workflow designed to surface locations for further investigation—not to make unsupported claims about land-cover change.</p>
        </div>
        <div className="method-grid">
          <article className="method-card"><span className="method-number">01</span><div className="method-symbol">◉</div><h3>Observe</h3><p>Use multi-temporal Sentinel-2 Level-2A surface-reflectance scenes over the Aravalli study region.</p><span className="method-meta">SATELLITE DATA</span></article>
          <article className="method-card"><span className="method-number">02</span><div className="method-symbol">⌁</div><h3>Compare</h3><p>Calculate vegetation signals such as NDVI and compare observations across selected time periods.</p><span className="method-meta">NDVI BASELINE</span></article>
          <article className="method-card"><span className="method-number">03</span><div className="method-symbol">⌖</div><h3>Flag</h3><p>Apply persistence and scene-quality screening, then group spatially connected pixels into candidate polygons.</p><span className="method-meta">CANDIDATE GENERATION</span></article>
          <article className="method-card"><span className="method-number">04</span><div className="method-symbol">✓</div><h3>Review</h3><p>Inspect candidate geometry and attributes, then record confirmed, rejected or still-pending review status.</p><span className="method-meta">HUMAN VERIFICATION</span></article>
        </div>
      </section>

      <section className="interpret-section" id="interpretation">
        <div className="interpret-copy"><span className="section-kicker">READ THE RESULTS CAREFULLY</span><h2>A detection is a signal.<br /><em>Not a verdict.</em></h2><p>The baseline highlights locations with vegetation-index change patterns that meet the configured screening criteria. Similar signals can also arise from seasonal vegetation cycles, atmospheric effects, land management or differences between satellite observations.</p></div>
        <div className="interpret-points">
          <div><span className="point-mark">01</span><p><strong>Candidate area</strong><small>Summed area of polygons flagged by the current detection run. It is not an estimate of confirmed deforestation.</small></p></div>
          <div><span className="point-mark">02</span><p><strong>Confidence score</strong><small>An algorithmic score used to help prioritize inspection. It is not a calibrated probability of vegetation loss.</small></p></div>
          <div><span className="point-mark">03</span><p><strong>Verification status</strong><small>Candidate, confirmed and rejected are review labels. Confirmation requires independent visual or field evidence.</small></p></div>
        </div>
      </section>

      <footer className="footer"><a className="brand" href="#overview"><span className="brand-mark">F</span><span>Forest<span className="brand-light">Watch</span></span></a><span>Remote sensing research prototype · Aravalli study region, Delhi NCR</span><a href="#overview">Back to top ↑</a></footer>
    </main>
  );
}
