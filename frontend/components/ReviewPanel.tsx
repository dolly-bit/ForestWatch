"use client";
import { useEffect, useState } from "react";
import type { EventFeature, EventStatus } from "@/lib/api";

interface Props {
  feature: EventFeature | null;
  onReview: (id: number, status: EventStatus, note: string) => Promise<void>;
}

export default function ReviewPanel({ feature, onReview }: Props) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => setNote(feature?.properties.note ?? ""), [feature?.properties.id, feature?.properties.note]);

  if (!feature) return <p className="muted">Click a flagged area on the map to review it.</p>;
  const p = feature.properties;

  const act = async (status: EventStatus) => {
    setBusy(true);
    try { await onReview(p.id, status, note); } finally { setBusy(false); }
  };

  return (
    <div>
      <div className="stat"><span>Area</span><b>{p.area_ha.toFixed(2)} ha</b></div>
      <div className="stat"><span>Confidence</span><b>{p.confidence == null ? "n/a" : p.confidence.toFixed(2)}</b></div>
      <div className="stat"><span>Status</span><span className="badge">{p.status}</span></div>
      <p className="muted">
        This is a <b>candidate</b> found by an algorithm. Confidence is a model score, not a probability
        of real deforestation. Confirm only after visual or field verification.
      </p>
      <label>Note</label>
      <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. visible clearing next to road" />
      <div className="row" style={{ marginTop: 8 }}>
        <button className="primary" disabled={busy} onClick={() => act("confirmed")}>Confirm</button>
        <button className="danger" disabled={busy} onClick={() => act("rejected")}>Reject</button>
        <button disabled={busy} onClick={() => act("candidate")}>Reset</button>
      </div>
    </div>
  );
}
