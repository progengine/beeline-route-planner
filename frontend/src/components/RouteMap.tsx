import { useEffect, useRef } from "react";
import L from "leaflet";
import type { Engineer, PlanResult, Request } from "../types";

const COLORS = [
  "#e6b800", "#3d8bfd", "#2ecc71", "#ff6bb5", "#9b7bff",
  "#ff8c42", "#00c2d4", "#ef5b5b", "#7cbf2e", "#d946ef",
  "#38bdf8", "#f59e0b",
];

const SKILL_RU: Record<string, string> = {
  local_works: "Локальные работы",
  connection_and_orders: "Подключение и дозаказы",
  emergency_works: "Аварийные работы",
};

interface Props {
  engineers: Engineer[];
  requests: Request[];
  plan: PlanResult | null;
  selectedId: string | null;
  selectedEngineerId: string | null;
  onSelect: (requestId: string) => void;
  onSelectEngineer: (engineerId: string) => void;
}

async function fetchRoadLine(
  from: { lat: number; lon: number },
  to: { lat: number; lon: number },
): Promise<L.LatLngExpression[]> {
  try {
    const url =
      `/api/geo/route?from_lat=${from.lat}&from_lon=${from.lon}` +
      `&to_lat=${to.lat}&to_lon=${to.lon}&vehicle=car`;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 5000);
    const res = await fetch(url, { signal: ctrl.signal });
    clearTimeout(timer);
    if (!res.ok) throw new Error("geo fail");
    const data = await res.json();
    const coords = data.coordinates as number[][];
    if (!coords?.length) throw new Error("empty");
    return coords.map((c) => [c[0], c[1]] as L.LatLngExpression);
  } catch {
    // короткая «ломаная» вместо сквозной прямой через весь город
    const midLat = (from.lat + to.lat) / 2;
    const midLon = (from.lon + to.lon) / 2;
    return [
      [from.lat, from.lon],
      [midLat, midLon],
      [to.lat, to.lon],
    ];
  }
}

export function RouteMap({
  engineers,
  requests,
  plan,
  selectedId,
  selectedEngineerId,
  onSelect,
  onSelectEngineer,
}: Props) {
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: [55.72, 37.75],
      zoom: 12,
      zoomControl: true,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    setTimeout(() => map.invalidateSize(), 150);
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    let cancelled = false;

    async function draw() {
      layer!.clearLayers();
      const reqMap = new Map(requests.map((r) => [r.id, r]));
      const engMap = new Map(engineers.map((e) => [e.id, e]));
      const focus = selectedEngineerId;
      const bounds: L.LatLngExpression[] = [];

      // request_id → engineer_id
      const owner = new Map<string, string>();
      if (plan) {
        for (const route of plan.routes) {
          for (const s of route.stops) owner.set(s.request_id, route.engineer_id);
        }
      }

      // точки заявок
      for (const r of requests) {
        if (!r.coordinates) continue;
        const eid = owner.get(r.id);
        const assigned = !!eid;
        const isFocusRoute = focus && eid === focus;
        const isDimmed = focus && eid && eid !== focus;
        const isSel = selectedId === r.id;

        let radius = isSel ? 10 : 7;
        let color = "#888";
        let fill = "#aaa";
        let opacity = 1;

        if (!assigned) {
          color = "#c0392b";
          fill = "#e74c3c";
          if (focus) opacity = 0.25;
        } else if (isFocusRoute || (!focus && assigned)) {
          const idx =
            plan?.routes.findIndex((rt) => rt.engineer_id === eid) ?? 0;
          color = COLORS[idx % COLORS.length];
          fill = isSel ? "#f0c400" : color;
          opacity = 1;
          radius = isFocusRoute ? 9 : radius;
        } else if (isDimmed) {
          color = "#555";
          fill = "#777";
          opacity = 0.22;
        }

        const m = L.circleMarker([r.coordinates.lat, r.coordinates.lon], {
          radius,
          color,
          fillColor: fill,
          fillOpacity: opacity,
          opacity,
          weight: isSel || isFocusRoute ? 3 : 2,
        });
        const skill = SKILL_RU[r.required_skill] || r.required_skill;
        const engName = eid ? engMap.get(eid)?.name || eid : "не назначена";
        m.bindTooltip(
          `<b>${r.id}</b><br/>${r.address || ""}<br/>${skill}<br/>${engName}`,
          { sticky: true },
        );
        m.on("click", () => {
          onSelect(r.id);
          if (eid) onSelectEngineer(eid);
        });
        m.addTo(layer!);
        if (!isDimmed) bounds.push([r.coordinates.lat, r.coordinates.lon]);
      }

      if (!plan) {
        if (bounds.length) map!.fitBounds(L.latLngBounds(bounds), { padding: [40, 40] });
        return;
      }

      // маршруты: только по дорогам, без сквозных диагоналей
      for (let idx = 0; idx < plan.routes.length; idx++) {
        if (cancelled) return;
        const route = plan.routes[idx];
        const color = COLORS[idx % COLORS.length];
        const eng = engMap.get(route.engineer_id);
        const isFocus = !focus || focus === route.engineer_id;
        const lineOpacity = isFocus ? 0.95 : 0.12;
        const lineWeight = isFocus ? 5 : 2;

        const points: { lat: number; lon: number }[] = [];
        if (eng) {
          points.push({
            lat: eng.start_coordinates.lat,
            lon: eng.start_coordinates.lon,
          });
          L.circleMarker(
            [eng.start_coordinates.lat, eng.start_coordinates.lon],
            {
              radius: isFocus ? 8 : 4,
              color: isFocus ? "#111" : "#666",
              fillColor: isFocus ? color : "#888",
              fillOpacity: isFocus ? 1 : 0.25,
              opacity: isFocus ? 1 : 0.25,
              weight: 2,
            },
          )
            .bindTooltip(`База: ${eng.name || eng.id}`)
            .on("click", () => onSelectEngineer(route.engineer_id))
            .addTo(layer!);
          if (isFocus) {
            bounds.push([eng.start_coordinates.lat, eng.start_coordinates.lon]);
          }
        }

        for (const stop of route.stops) {
          const r = reqMap.get(stop.request_id);
          if (r?.coordinates) {
            points.push({ lat: r.coordinates.lat, lon: r.coordinates.lon });
          }
        }

        for (let i = 0; i < points.length - 1; i++) {
          if (cancelled) return;
          // для заблюренных маршрутов не ждём OSRM — короткая ломаная
          let line: L.LatLngExpression[];
          if (!isFocus) {
            line = [
              [points[i].lat, points[i].lon],
              [points[i + 1].lat, points[i + 1].lon],
            ];
          } else {
            line = await fetchRoadLine(points[i], points[i + 1]);
          }
          if (cancelled) return;
          L.polyline(line, {
            color: isFocus ? color : "#666",
            weight: lineWeight,
            opacity: lineOpacity,
          }).addTo(layer!);
          if (isFocus) bounds.push(...line);
        }
      }

      if (bounds.length && map) {
        map.fitBounds(L.latLngBounds(bounds), { padding: [48, 48], maxZoom: 14 });
      }
    }

    draw();
    return () => {
      cancelled = true;
    };
  }, [
    engineers,
    requests,
    plan,
    selectedId,
    selectedEngineerId,
    onSelect,
    onSelectEngineer,
  ]);

  return <div id="map" ref={containerRef} />;
}
