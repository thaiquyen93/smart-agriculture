// ============================================================================
// SMURF Smart Agriculture — Device Constants & Theme Config
// ============================================================================

import { DeviceCode } from './types';

/** Device display metadata: name, icon emoji, color theme, unit for primary metric */
export const DEVICE_CONFIG: Record<DeviceCode, {
  name: string;
  label: string;
  icon: string;
  color: string;       // Tailwind bg- prefix color
  borderColor: string;
  textColor: string;
  metrics: { key: string; label: string; unit: string }[];
}> = {
  SOIL_01: {
    name: 'SOIL_01',
    label: 'Soil Moisture',
    icon: '💧',
    color: 'bg-emerald-500/10',
    borderColor: 'border-emerald-500/30',
    textColor: 'text-emerald-400',
    metrics: [
      { key: 'soil_moisture', label: 'SOIL MOISTURE', unit: '%' },
      { key: 'temperature', label: 'SOIL TEMP', unit: '°C' },
    ],
  },
  WEATHER_01: {
    name: 'WEATHER_01',
    label: 'Weather Station',
    icon: '🌤️',
    color: 'bg-sky-500/10',
    borderColor: 'border-sky-500/30',
    textColor: 'text-sky-400',
    metrics: [
      { key: 'temperature', label: 'TEMPERATURE', unit: '°C' },
      { key: 'humidity', label: 'HUMIDITY', unit: '%' },
    ],
  },
  PUMP_01: {
    name: 'PUMP_01',
    label: 'Irrigation Pump',
    icon: '⚙️',
    color: 'bg-indigo-500/10',
    borderColor: 'border-indigo-500/30',
    textColor: 'text-indigo-400',
    metrics: [
      { key: 'flow_rate', label: 'FLOW RATE', unit: 'L/min' },
      { key: 'power', label: 'POWER', unit: 'W' },
    ],
  },
  PH_01: {
    name: 'PH_01',
    label: 'pH Sensor',
    icon: '🧪',
    color: 'bg-purple-500/10',
    borderColor: 'border-purple-500/30',
    textColor: 'text-purple-400',
    metrics: [
      { key: 'ph', label: 'pH LEVEL', unit: 'pH' },
    ],
  },
  TANK_01: {
    name: 'TANK_01',
    label: 'Water Tank',
    icon: '🪣',
    color: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500/30',
    textColor: 'text-cyan-400',
    metrics: [
      { key: 'level', label: 'WATER LEVEL', unit: '%' },
    ],
  },
  SUN_01: {
    name: 'SUN_01',
    label: 'Sunlight Sensor',
    icon: '☀️',
    color: 'bg-amber-500/10',
    borderColor: 'border-amber-500/30',
    textColor: 'text-amber-400',
    metrics: [
      { key: 'lux', label: 'SUNLIGHT', unit: 'Lux' },
    ],
  },
};

/** Get the status badge for a metric value */
export function getMetricStatus(deviceId: DeviceCode, metricKey: string, value: number): {
  label: string;
  color: string;
} {
  if (deviceId === 'SOIL_01' && metricKey === 'soil_moisture') {
    if (value >= 50 && value <= 80) return { label: 'Optimal', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' };
    if (value >= 30 && value < 50) return { label: 'Monitor', color: 'text-amber-400 bg-amber-500/20 border-amber-500/30' };
    if (value < 30) return { label: 'Low!', color: 'text-rose-400 bg-rose-500/20 border-rose-500/30' };
    return { label: 'High', color: 'text-sky-400 bg-sky-500/20 border-sky-500/30' };
  }
  if (metricKey === 'temperature') {
    if (value >= 20 && value <= 35) return { label: 'Normal', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' };
    if (value > 35) return { label: 'Hot!', color: 'text-rose-400 bg-rose-500/20 border-rose-500/30' };
    return { label: 'Cold', color: 'text-sky-400 bg-sky-500/20 border-sky-500/30' };
  }
  if (metricKey === 'humidity') {
    if (value >= 40 && value <= 80) return { label: 'Normal', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' };
    return { label: 'Monitor', color: 'text-amber-400 bg-amber-500/20 border-amber-500/30' };
  }
  if (metricKey === 'ph') {
    if (value >= 6.0 && value <= 7.5) return { label: 'Optimal', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' };
    return { label: 'Check', color: 'text-amber-400 bg-amber-500/20 border-amber-500/30' };
  }
  if (metricKey === 'level') {
    if (value >= 60) return { label: 'Good', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' };
    if (value >= 30) return { label: 'Low', color: 'text-amber-400 bg-amber-500/20 border-amber-500/30' };
    return { label: 'Critical!', color: 'text-rose-400 bg-rose-500/20 border-rose-500/30' };
  }
  if (metricKey === 'lux') {
    if (value >= 10000 && value <= 60000) return { label: 'Good', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' };
    if (value > 60000) return { label: 'Intense', color: 'text-amber-400 bg-amber-500/20 border-amber-500/30' };
    return { label: 'Low', color: 'text-sky-400 bg-sky-500/20 border-sky-500/30' };
  }
  if (metricKey === 'flow_rate') {
    if (value > 0) return { label: 'Active', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' };
    return { label: 'Off', color: 'text-gray-400 bg-gray-500/20 border-gray-500/30' };
  }
  if (metricKey === 'power') {
    if (value > 0) return { label: 'Running', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' };
    return { label: 'Idle', color: 'text-gray-400 bg-gray-500/20 border-gray-500/30' };
  }
  return { label: 'OK', color: 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' };
}

/** Agent display metadata */
export const AGENT_CONFIG: Record<string, { icon: string; color: string }> = {
  'FarmCoordinatorAgent': { icon: '🧠', color: 'text-emerald-400' },
  'FieldIoTAgent': { icon: '📡', color: 'text-sky-400' },
  'IrrigationPlanningAgent': { icon: '💧', color: 'text-cyan-400' },
  'ResourceAgent': { icon: '🪣', color: 'text-purple-400' },
  'FarmActionAgent': { icon: '⚡', color: 'text-amber-400' },
};

/** Freshness thresholds */
export const FRESHNESS = {
  LIVE_MS: 10_000,       // < 10s = live
  DELAYED_MS: 30_000,    // 10-30s = delayed
  STALE_MS: 60_000,      // > 60s = stale
};

/** Mock data for when no MQTT is available */
export const MOCK_DEVICES: Record<DeviceCode, Record<string, number>> = {
  SOIL_01: { soil_moisture: 42.5, temperature: 28.3 },
  WEATHER_01: { temperature: 31.0, humidity: 65.0 },
  PUMP_01: { flow_rate: 12.5, power: 750 },
  PH_01: { ph: 6.8 },
  TANK_01: { level: 82.0 },
  SUN_01: { lux: 52000 },
};
