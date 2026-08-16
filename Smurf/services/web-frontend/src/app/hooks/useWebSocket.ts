"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { DeviceTelemetry, AIForecast, AlertEvent, WSMessage, DeviceCode } from "../lib/types";
import { FRESHNESS, MOCK_DEVICES } from "../lib/constants";

interface WebSocketState {
  connected: boolean;
  devices: Record<string, DeviceTelemetry & { _receivedAt: number }>;
  forecasts: Record<string, AIForecast>;
  alerts: AlertEvent[];
  useMock: boolean;
}

/**
 * Custom hook managing the WebSocket lifecycle.
 * Auto-reconnects with exponential backoff.
 * Falls back to mock data after 5s if no real data arrives.
 */
export function useWebSocket() {
  const [state, setState] = useState<WebSocketState>({
    connected: false,
    devices: {},
    forecasts: {},
    alerts: [],
    useMock: false,
  });

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);
  const mockTimer = useRef<NodeJS.Timeout | null>(null);
  const hasReceivedData = useRef(false);

  // Start mock data generation if no real data after 5s
  const startMockFallback = useCallback(() => {
    if (hasReceivedData.current) return;

    setState((prev) => ({ ...prev, useMock: true }));

    // Generate initial mock data
    const mockDevices: Record<string, DeviceTelemetry & { _receivedAt: number }> = {};
    const deviceCodes: DeviceCode[] = ['SOIL_01', 'WEATHER_01', 'PUMP_01', 'PH_01', 'TANK_01', 'SUN_01'];

    deviceCodes.forEach((id) => {
      mockDevices[id] = {
        device_id: id,
        ...MOCK_DEVICES[id],
        timestamp: Date.now() / 1000,
        _receivedAt: Date.now(),
      };
    });

    setState((prev) => ({ ...prev, devices: mockDevices, useMock: true }));

    // Periodically jitter mock data to simulate live updates
    mockTimer.current = setInterval(() => {
      setState((prev) => {
        if (hasReceivedData.current) return prev; // stop if real data arrives
        const updated = { ...prev.devices };
        deviceCodes.forEach((id) => {
          const base = MOCK_DEVICES[id];
          const jittered: Record<string, any> = {};
          Object.entries(base).forEach(([k, v]) => {
            jittered[k] = +(v + (Math.random() - 0.5) * v * 0.05).toFixed(2);
          });
          updated[id] = {
            ...updated[id],
            ...jittered,
            timestamp: Date.now() / 1000,
            _receivedAt: Date.now(),
          };
        });
        return { ...prev, devices: updated };
      });
    }, 3000);
  }, []);

  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
    let retryDelay = 1000;

    function connect() {
      try {
        const socket = new WebSocket(wsUrl);
        socketRef.current = socket;

        socket.onopen = () => {
          setState((prev) => ({ ...prev, connected: true }));
          retryDelay = 1000;
        };

        socket.onmessage = (event) => {
          try {
            const msg: WSMessage = JSON.parse(event.data);
            hasReceivedData.current = true;

            setState((prev) => {
              const next = { ...prev, useMock: false };

              if (msg.type === "TELEMETRY_RAW") {
                const data = msg.data as DeviceTelemetry;
                const key = data.device_id || data.station_id || "UNKNOWN";
                next.devices = {
                  ...prev.devices,
                  [key]: { ...data, _receivedAt: Date.now() },
                };
              } else if (msg.type === "AI_FORECAST") {
                const data = msg.data as AIForecast;
                const key = data.station_id || "UNKNOWN";
                next.forecasts = { ...prev.forecasts, [key]: data };
              } else if (msg.type === "ALERT_EVENT") {
                next.alerts = [msg.data as AlertEvent, ...prev.alerts.slice(0, 19)];
              }

              return next;
            });
          } catch (e) {
            console.error("[WS] Parse error:", e);
          }
        };

        socket.onclose = () => {
          setState((prev) => ({ ...prev, connected: false }));
          reconnectTimer.current = setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 1.5, 10000);
        };

        socket.onerror = () => {
          socket.close();
        };
      } catch {
        reconnectTimer.current = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 1.5, 10000);
      }
    }

    connect();

    // Fallback to mock after 5s
    const fallbackTimer = setTimeout(startMockFallback, 5000);

    return () => {
      if (socketRef.current) socketRef.current.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (mockTimer.current) clearInterval(mockTimer.current);
      clearTimeout(fallbackTimer);
    };
  }, [startMockFallback]);

  /** Get freshness status for a device */
  const getFreshness = useCallback(
    (deviceId: string): "live" | "delayed" | "stale" => {
      const device = state.devices[deviceId];
      if (!device) return "stale";
      const age = Date.now() - device._receivedAt;
      if (age < FRESHNESS.LIVE_MS) return "live";
      if (age < FRESHNESS.DELAYED_MS) return "delayed";
      return "stale";
    },
    [state.devices]
  );

  return {
    connected: state.connected,
    devices: state.devices,
    deviceList: Object.values(state.devices),
    forecasts: state.forecasts,
    forecastList: Object.values(state.forecasts),
    alerts: state.alerts,
    useMock: state.useMock,
    getFreshness,
  };
}
