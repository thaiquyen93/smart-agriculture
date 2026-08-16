// ============================================================================
// SMURF Smart Agriculture — TypeScript Data Models
// Maps to: database-saver/db.py schema + MQTT device codes from Track B
// ============================================================================

export type DeviceCode = 'SOIL_01' | 'WEATHER_01' | 'PUMP_01' | 'PH_01' | 'TANK_01' | 'SUN_01';

export interface SensorReading {
  deviceId: string;
  zoneId: string;
  metric: string;
  value: number;
  unit: string;
  timestamp: string;
  status: "online" | "offline" | "stale";
}

export interface AIInsight {
  zoneId: string;
  prediction: string;
  confidence: number;
  priority: "low" | "medium" | "high" | "critical";
  factors: string[];
  recommendation: string;
  evidenceId: string;
}

export interface Plan {
  id: string;
  zoneId: string;
  action: string;
  responsibleAgent: string;
  status:
    | "detected"
    | "analyzing"
    | "recommended"
    | "pending_approval"
    | "approved"
    | "executing"
    | "verified"
    | "failed";
  createdAt: string;
  duration?: string;
  expectedUsage?: string;
  reason?: string;
}

export interface Verification {
  expected: string;
  actual: string;
  status: "passed" | "failed";
}

export interface TaskItem {
  id: string;
  title: string;
  zone: string;
  responsible: string;
  priority: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  status: string;
  dueTime: string;
}

/** Raw telemetry from a single device (via WebSocket TELEMETRY_RAW) */
export interface DeviceTelemetry {
  device_id: DeviceCode;
  station_id?: string;
  timestamp: number;
  soil_moisture?: number;
  temperature?: number;
  humidity?: number;
  flow_rate?: number;
  power?: number;
  status?: string;
  ph?: number;
  level?: number;
  lux?: number;
  pressure?: number;
  protocol?: string;
  [key: string]: any;
}

export interface WindowData {
  device_id: string;
  window_type: string;
  metrics: Record<string, number>;
  anomalies?: string[];
  timestamp: number;
}

/** Multi-Agent reasoning trace log entry */
export interface AgentLogEntry {
  session_id: string;
  agent_name: string;
  action_type: string;
  input_prompt: string;
  output_response: string;
  evidence_data: Record<string, any>;
  created_at: number;
}

export interface WSMessage {
  type: 'TELEMETRY_RAW' | 'WINDOW_MINUTE' | 'WINDOW_HOURLY' | 'ALERT_EVENT' | 'AI_FORECAST';
  data: any;
  timestamp: number;
}

export type TabId = "home" | "dashboard" | "chat" | "profile";

export interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  content: string;
  timestamp: number;
  agent_name?: string;
  data_sources?: string[];
}

export interface IrrigationPlan {
  plan_id: string;
  area_id: string;
  status: 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | string;
  suggested_time: string;
  water_amount_liters: number;
  reasoning_summary: string;
  data_evidence?: { device_id: string; value: number; unit: string }[];
  verification_result?: { message: string };
}

export interface AIForecast {
  station_id: string;
  prediction: string;
  confidence?: number;
  [key: string]: any;
}

export interface AlertEvent {
  id: string;
  type: string;
  message: string;
  severity: string;
  timestamp: number;
  [key: string]: any;
}



