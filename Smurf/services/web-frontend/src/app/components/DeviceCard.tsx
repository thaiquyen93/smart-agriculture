"use client";

import React from "react";
import { DeviceTelemetry, DeviceCode } from "../lib/types";
import { DEVICE_CONFIG, getMetricStatus } from "../lib/constants";

interface DeviceCardProps {
  device: DeviceTelemetry & { _receivedAt: number };
  freshness: "live" | "delayed" | "stale";
}

/** Sensor card styling per device — matching reference image's left-accent card design */
const CARD_ACCENT: Record<DeviceCode, string> = {
  SOIL_01: "sensor-card-emerald",
  WEATHER_01: "sensor-card-sky",
  PUMP_01: "sensor-card-indigo",
  PH_01: "sensor-card-purple",
  TANK_01: "sensor-card-cyan",
  SUN_01: "sensor-card-amber",
};

export default function DeviceCard({ device, freshness }: DeviceCardProps) {
  const deviceId = device.device_id as DeviceCode;
  const config = DEVICE_CONFIG[deviceId];
  if (!config) return null;

  const primaryMetric = config.metrics[0];
  const primaryValue = device[primaryMetric.key as keyof DeviceTelemetry] as number | undefined;

  // Determine status for the primary metric
  const status = primaryValue !== undefined
    ? getMetricStatus(deviceId, primaryMetric.key, primaryValue)
    : { label: "No Data", color: "text-gray-400 bg-gray-500/20 border-gray-500/30" };

  // Format large numbers
  const formatValue = (v: number | undefined, unit: string) => {
    if (v === undefined || v === null) return "--";
    if (unit === "Lux" && v >= 1000) return `${(v / 1000).toFixed(1)}k`;
    if (unit === "W" && v >= 1000) return `${(v / 1000).toFixed(1)}kW`;
    return v % 1 === 0 ? v.toString() : v.toFixed(1);
  };

  // Freshness age text
  const ageText = (() => {
    const ageSec = Math.floor((Date.now() - device._receivedAt) / 1000);
    if (ageSec < 5) return "just now";
    if (ageSec < 60) return `${ageSec}s ago`;
    return `${Math.floor(ageSec / 60)}m ago`;
  })();

  return (
    <div className={`sensor-card ${CARD_ACCENT[deviceId] || ""} fade-in-up`}>
      <div className="flex items-center justify-between">
        {/* Left: Icon + Label + Value */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {/* Freshness dot */}
            <span
              className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                freshness === "live"
                  ? "bg-emerald-400 live-pulse"
                  : freshness === "delayed"
                  ? "bg-amber-400"
                  : "bg-rose-400 stale-blink"
              }`}
            />
            <span className="text-[11px] font-medium tracking-wider uppercase text-gray-400">
              {primaryMetric.label}
            </span>
          </div>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-white tracking-tight">
              {config.icon} {formatValue(primaryValue, primaryMetric.unit)}
            </span>
            <span className="text-sm text-gray-500 font-medium">{primaryMetric.unit}</span>
          </div>

          {/* Secondary metrics (if any) */}
          {config.metrics.length > 1 && (
            <div className="flex items-center gap-3 mt-2">
              {config.metrics.slice(1).map((m) => {
                const val = device[m.key as keyof DeviceTelemetry] as number | undefined;
                return (
                  <span key={m.key} className="text-xs text-gray-500 font-mono">
                    {m.label}: <span className="text-gray-300">{formatValue(val, m.unit)}{m.unit}</span>
                  </span>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: Status badge */}
        <div className="flex flex-col items-end gap-2 flex-shrink-0 ml-3">
          <span className={`status-badge ${status.color}`}>
            {status.label}
          </span>
          <span className="text-[10px] text-gray-600 font-mono">{ageText}</span>
        </div>
      </div>

      {/* Progress bar for moisture/level metrics */}
      {(primaryMetric.key === "soil_moisture" || primaryMetric.key === "level") && primaryValue !== undefined && (
        <div className="mt-3 w-full bg-gray-900 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full rounded-full animate-fill transition-all duration-500 ${
              primaryValue > 60 ? "bg-emerald-500" : primaryValue > 30 ? "bg-amber-500" : "bg-rose-500"
            }`}
            style={{ width: `${Math.min(primaryValue, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}
