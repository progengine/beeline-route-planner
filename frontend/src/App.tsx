import { useCallback, useEffect, useMemo, useState } from "react";
import { comparePlans, replan } from "./api";
import { RouteMap } from "./components/RouteMap";
import type { CompareResponse, PlanResult, Scenario } from "./types";

type Mode = "optimized" | "baseline";

const SKILL_RU: Record<string, string> = {
  local_works: "Локальные работы",
  connection_and_orders: "Подключение и дозаказы",
  emergency_works: "Аварийные работы",
};


export default function App() {
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [compare, setCompare] = useState<CompareResponse | null>(null);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [mode, setMode] = useState<Mode>("optimized");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedEngineerId, setSelectedEngineerId] = useState<string | null>(null);
  const [tab, setTab] = useState<"routes" | "jobs" | "unassigned">("routes");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setBanner(null);
    try {
      const scRes = await fetch("/api/scenario/demo");
      if (!scRes.ok) throw new Error("Нет связи с API. Запустите backend на :8000");
      const sc = await scRes.json();
      setScenario(sc);
      const nReq = sc.requests?.length ?? 0;
      const nEng = sc.engineers?.length ?? 0;
      setBanner(`Данные с бэка: ${nReq} заявок, ${nEng} инженеров — считаем план…`);

      const cmp = await comparePlans({
        engineers: sc.engineers,
        requests: sc.requests,
      });
      setCompare(cmp);
      setPlan(cmp.optimized);
      setMode("optimized");
      setBanner(
        `Готово: ${nReq} заявок, ${nEng} инженеров · оптимум ${cmp.optimized.metrics.engineers_used} инж. / ${cmp.optimized.metrics.total_distance_km.toFixed(1)} км`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const engName = useMemo(() => {
    const m = new Map<string, string>();
    scenario?.engineers.forEach((e) => m.set(e.id, e.name || e.id));
    return m;
  }, [scenario]);

  const reqMap = useMemo(() => {
    const m = new Map<string, Scenario["requests"][0]>();
    scenario?.requests.forEach((r) => m.set(r.id, r));
    return m;
  }, [scenario]);

  function switchMode(m: Mode) {
    if (!compare) return;
    setMode(m);
    setPlan(m === "baseline" ? compare.baseline : compare.optimized);
    setBanner(null);
  }

  async function runEvent(
    type: "new_urgent_request" | "cancel_request" | "engineer_unavailable",
  ) {
    if (!scenario || !plan) return;
    setLoading(true);
    setError(null);
    try {
      let event: Record<string, unknown> = {
        type,
        event_time: "14:00:00",
      };
      if (type === "cancel_request") {
        const rid =
          plan.routes[0]?.stops[0]?.request_id || scenario.requests[0]?.id;
        event = { ...event, request_id: rid };
      } else if (type === "engineer_unavailable") {
        const eid = plan.routes[0]?.engineer_id || scenario.engineers[0]?.id;
        event = { ...event, engineer_id: eid };
      } else {
        event = {
          ...event,
          new_request: {
            id: `URG-${Date.now()}`,
            address: "Срочная заявка (демо)",
            coordinates: { lat: 55.715, lon: 37.76 },
            duration_minutes: 45,
            window_start: "15:00:00",
            window_end: "17:00:00",
            priority: "urgent",
            required_skill: "local_works",
          },
        };
      }
      const next = await replan({
        engineers: scenario.engineers,
        requests: scenario.requests,
        event,
        previous_plan: plan,
        mode: "optimized",
      });
      setPlan(next);
      setMode("optimized");
      setBanner(
        `Перепланирование: ${type}. Изменено назначений: ${next.changed_request_ids.length}`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const metrics = plan?.metrics;
  const explanation = selectedId && plan?.explanations?.[selectedId];

  return (
    <div className="app">
      <header>
        <h1>
          <span>Полевой</span> · диспетчер Билайн Бизнес
        </h1>
        <div className="toolbar">
          <button
            className={mode === "optimized" ? "active primary" : ""}
            onClick={() => switchMode("optimized")}
            disabled={!compare}
          >
            Оптимум
          </button>
          <button
            className={mode === "baseline" ? "active" : ""}
            onClick={() => switchMode("baseline")}
            disabled={!compare}
          >
            Baseline
          </button>
          <button onClick={() => runEvent("new_urgent_request")} disabled={loading}>
            Срочная
          </button>
          <button onClick={() => runEvent("cancel_request")} disabled={loading}>
            Отмена
          </button>
          <button
            onClick={() => runEvent("engineer_unavailable")}
            disabled={loading}
          >
            Недоступен
          </button>
          <button onClick={load} disabled={loading}>
            Сброс
          </button>
          {selectedEngineerId && (
            <button
              onClick={() => {
                setSelectedEngineerId(null);
                setSelectedId(null);
              }}
            >
              Все маршруты
            </button>
          )}
          <span className="status">{loading ? "считаем…" : "готово"}</span>
        </div>
      </header>

      <div className="metrics">
        <div className="metric">
          <div className="label">Инженеров</div>
          <div className="value">{metrics?.engineers_used ?? "—"}</div>
        </div>
        <div className="metric">
          <div className="label">Пробег, км</div>
          <div className="value">
            {metrics ? metrics.total_distance_km.toFixed(1) : "—"}
          </div>
        </div>
        <div className="metric">
          <div className="label">Назначено</div>
          <div className="value">
            {plan
              ? plan.routes.reduce((n, r) => n + r.stops.length, 0)
              : "—"}
          </div>
        </div>
        <div className="metric">
          <div className="label">
            {compare ? "Δ vs baseline, км" : "Неназнач."}
          </div>
          <div className="value">
            {mode === "optimized" && compare
              ? `−${compare.delta_distance_km.toFixed(1)}`
              : (plan?.unassigned.length ?? "—")}
          </div>
        </div>
      </div>

      {banner && <div className="banner">{banner}</div>}
      {error && <div className="error">{error}</div>}

      <div className="main">
        <RouteMap
          engineers={scenario?.engineers || []}
          requests={scenario?.requests || []}
          plan={plan}
          selectedId={selectedId}
          selectedEngineerId={selectedEngineerId}
          onSelect={setSelectedId}
          onSelectEngineer={setSelectedEngineerId}
        />
        <aside className="sidebar">
          <div className="tabs">
            <button
              className={tab === "routes" ? "active" : ""}
              onClick={() => setTab("routes")}
            >
              Маршруты
            </button>
            <button
              className={tab === "jobs" ? "active" : ""}
              onClick={() => setTab("jobs")}
            >
              Заявки
            </button>
            <button
              className={tab === "unassigned" ? "active" : ""}
              onClick={() => setTab("unassigned")}
            >
              Вне плана
            </button>
          </div>

          <div className="card">
            <h3>Почему так</h3>
            <div className="meta">
              {explanation ||
                "Нажмите на заявку на карте или в списке маршрута — здесь появится объяснение назначения."}
            </div>
          </div>

          {tab === "routes" &&
            plan?.routes.map((route) => (
              <div
                className="card"
                key={route.engineer_id}
                onClick={() =>
                  setSelectedEngineerId((prev) =>
                    prev === route.engineer_id ? null : route.engineer_id,
                  )
                }
                style={{
                  cursor: "pointer",
                  outline:
                    selectedEngineerId === route.engineer_id
                      ? "2px solid var(--yellow)"
                      : undefined,
                  opacity:
                    selectedEngineerId && selectedEngineerId !== route.engineer_id
                      ? 0.45
                      : 1,
                }}
              >
                <h3>{engName.get(route.engineer_id) || route.engineer_id}</h3>
                <div className="meta">
                  {route.stops.length} точек · {route.total_distance_km.toFixed(1)} км
                </div>
                {route.stops.map((s) => {
                  const req = reqMap.get(s.request_id);
                  const changed = plan.changed_request_ids?.includes(s.request_id);
                  return (
                    <div
                      className="stop"
                      key={s.request_id}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedId(s.request_id);
                        setSelectedEngineerId(route.engineer_id);
                      }}
                    >
                      <span>
                        {changed && <span className="badge changed">изм.</span>}
                        {req?.priority === "urgent" && (
                          <span className="badge urgent">сроч.</span>
                        )}
                        {s.request_id}
                      </span>
                      <span>
                        {String(s.planned_start).slice(0, 5)}–{String(s.planned_end).slice(0, 5)}
                      </span>
                    </div>
                  );
                })}
              </div>
            ))}

          {tab === "jobs" &&
            scenario?.requests.map((r) => (
              <div
                className="card"
                key={r.id}
                onClick={() => setSelectedId(r.id)}
                style={{ cursor: "pointer" }}
              >
                <h3>
                  {r.priority === "urgent" && (
                    <span className="badge urgent">сроч.</span>
                  )}
                  {r.id}
                </h3>
                <div className="meta">
                  {r.address}
                  <br />
                  {String(r.window_start).slice(0, 5)}–{String(r.window_end).slice(0, 5)} ·{" "}
                  {SKILL_RU[r.required_skill] || r.required_skill}
                </div>
              </div>
            ))}

          {tab === "unassigned" &&
            (plan?.unassigned.length ? (
              plan.unassigned.map((u) => (
                <div className="card" key={u.request_id}>
                  <h3>{u.request_id}</h3>
                  <div className="meta">{u.explanation}</div>
                </div>
              ))
            ) : (
              <div className="meta">Все заявки назначены</div>
            ))}
        </aside>
      </div>
    </div>
  );
}
