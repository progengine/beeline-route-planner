import type { CompareResponse, PlanResult, Scenario } from "./types";

const BASE = "/api";

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 60000);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text}`);
    }
    return res.json() as Promise<T>;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Таймаут запроса к API (60с). Проверьте backend.");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export function fetchScenario(): Promise<Scenario> {
  return json("/scenario/demo");
}

export function comparePlans(body: {
  engineers: Scenario["engineers"];
  requests: Scenario["requests"];
}): Promise<CompareResponse> {
  return json("/plan/compare", { method: "POST", body: JSON.stringify(body) });
}

export function planMode(body: {
  engineers: Scenario["engineers"];
  requests: Scenario["requests"];
  mode: "greedy" | "optimized";
}): Promise<PlanResult> {
  return json("/plan", { method: "POST", body: JSON.stringify(body) });
}

export function replan(body: {
  engineers: Scenario["engineers"];
  requests: Scenario["requests"];
  event: Record<string, unknown>;
  previous_plan?: PlanResult | null;
  mode?: string;
}): Promise<PlanResult> {
  return json("/replan", {
    method: "POST",
    body: JSON.stringify({ mode: "optimized", ...body }),
  });
}
