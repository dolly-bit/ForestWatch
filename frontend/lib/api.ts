export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type EventStatus = "candidate" | "confirmed" | "rejected";

export interface EventProps {
  id: number;
  job_id: number;
  status: EventStatus;
  area_ha: number;
  n_pixels: number;
  confidence: number | null;
  note: string | null;
}
export interface EventFeature {
  type: "Feature";
  id: number;
  geometry: { type: "Polygon"; coordinates: number[][][] };
  properties: EventProps;
}
export interface EventCollection {
  type: "FeatureCollection";
  features: EventFeature[];
}
export interface Job {
  id: number;
  status: "queued" | "running" | "completed" | "failed";
  method: "baseline" | "unet";
  n_events: number;
  total_area_ha: number;
  error: string | null;
  created_at: string;
}
export interface Stats {
  job_id: number | null;
  by_status: Record<string, { count: number; area_ha: number }>;
  total_events: number;
  total_area_ha: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const getEvents = (minConfidence: number, status: string) => {
  const q = new URLSearchParams({ min_confidence: String(minConfidence) });
  if (status) q.set("status", status);
  return request<EventCollection>(`/change-events?${q.toString()}`);
};
export const getStats = () => request<Stats>("/stats");
export const getJobs = () => request<Job[]>("/jobs?limit=5");
export const createJob = (method: "baseline" | "unet", seasonal: boolean) =>
  request<Job>("/jobs", { method: "POST", body: JSON.stringify({ method, seasonal }) });
export const reviewEvent = (id: number, status: EventStatus, note: string) =>
  request<{ id: number; status: EventStatus; note: string | null }>(`/change-events/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status, note: note || null }),
  });
