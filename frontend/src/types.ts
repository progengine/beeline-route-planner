export type Skill = "local_works" | "connection_and_orders" | "emergency_works";
export type VehicleType = "car" | "walking" | "bicycle" | "public_transport";
export type Priority = "normal" | "urgent";

export interface Coordinates {
  lat: number;
  lon: number;
}

export interface Request {
  id: string;
  address?: string | null;
  coordinates?: Coordinates | null;
  duration_minutes: number;
  window_start: string;
  window_end: string;
  priority: Priority;
  required_skill: Skill;
  required_vehicle_type?: VehicleType | null;
}

export interface Engineer {
  id: string;
  name?: string | null;
  start_coordinates: Coordinates;
  shift_start: string;
  shift_end: string;
  skills: Skill[];
  vehicle_type: VehicleType;
}

export interface RouteStop {
  request_id: string;
  planned_arrival: string;
  planned_start: string;
  planned_end: string;
  travel_distance_km: number;
  travel_time_minutes: number;
}

export interface EngineerRoute {
  engineer_id: string;
  stops: RouteStop[];
  total_distance_km: number;
}

export interface UnassignedRequest {
  request_id: string;
  reason: string;
  explanation: string;
}

export interface PlanMetrics {
  engineers_used: number;
  distance_by_engineer_km: Record<string, number>;
  total_distance_km: number;
}

export interface PlanResult {
  routes: EngineerRoute[];
  unassigned: UnassignedRequest[];
  metrics: PlanMetrics;
  explanations: Record<string, string>;
  changed_request_ids: string[];
}

export interface Scenario {
  engineers: Engineer[];
  requests: Request[];
  meta: Record<string, unknown>;
}

export interface CompareResponse {
  baseline: PlanResult;
  optimized: PlanResult;
  delta_engineers: number;
  delta_distance_km: number;
}
