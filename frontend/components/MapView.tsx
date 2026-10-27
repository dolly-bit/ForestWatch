"use client";
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { EventCollection } from "@/lib/api";

interface Props {
  data: EventCollection;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  fitKey: number; // change this value to re-fit the view to the data
}

const EMPTY: EventCollection = { type: "FeatureCollection", features: [] };

export default function MapView({ data, selectedId, onSelect, fitKey }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const latest = useRef<EventCollection>(data);
  const onSelectRef = useRef(onSelect);
  latest.current = data;
  onSelectRef.current = onSelect;

  // create the map once
  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      } as maplibregl.StyleSpecification,
      center: [77.2, 28.4],
      zoom: 10,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.on("load", () => {
      map.addSource("events", { type: "geojson", data: latest.current as any });
      map.addLayer({
        id: "events-fill", type: "fill", source: "events",
        paint: {
          "fill-opacity": 0.45,
          "fill-color": [
            "case",
            ["==", ["get", "status"], "confirmed"], "#16a34a",
            ["==", ["get", "status"], "rejected"], "#6b7280",
            ["interpolate", ["linear"], ["coalesce", ["get", "confidence"], 0.5], 0, "#facc15", 1, "#dc2626"],
          ],
        },
      });
      map.addLayer({
        id: "events-line", type: "line", source: "events",
        paint: { "line-color": "#111827", "line-width": 1 },
      });
      map.addLayer({
        id: "events-selected", type: "line", source: "events", filter: ["==", ["get", "id"], -1],
        paint: { "line-color": "#38bdf8", "line-width": 3 },
      });
      map.on("click", "events-fill", (e) => {
        const f = e.features?.[0];
        if (f) onSelectRef.current(Number(f.properties?.id));
      });
      map.on("click", (e) => {
        if (!map.queryRenderedFeatures(e.point, { layers: ["events-fill"] }).length) onSelectRef.current(null);
      });
      map.on("mouseenter", "events-fill", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "events-fill", () => (map.getCanvas().style.cursor = ""));
      ready.current = true;
      (map.getSource("events") as maplibregl.GeoJSONSource).setData(latest.current as any);
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; ready.current = false; };
  }, []);

  // update data
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready.current) return;
    (map.getSource("events") as maplibregl.GeoJSONSource).setData((data ?? EMPTY) as any);
  }, [data]);

  // highlight selection
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready.current) return;
    map.setFilter("events-selected", ["==", ["get", "id"], selectedId ?? -1]);
  }, [selectedId, data]);

  // fit view to data
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data.features.length) return;
    const b = new maplibregl.LngLatBounds();
    data.features.forEach((f) => f.geometry.coordinates[0].forEach(([x, y]) => b.extend([x, y])));
    map.fitBounds(b, { padding: 60, maxZoom: 15, duration: 600 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);

  return <div ref={container} />;
}
