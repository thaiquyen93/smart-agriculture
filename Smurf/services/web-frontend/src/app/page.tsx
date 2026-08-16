"use client";

import React, { useEffect, useState } from "react";
import { Activity, ShieldAlert, Cpu, Radio, Zap, AlertTriangle, CheckCircle, Flame } from "lucide-react";

export default function ControlRoomPage() {
  const [wsConnected, setWsConnected] = useState(false);
  const [telemetry, setTelemetry] = useState<Record<string, any>>({});
  const [forecasts, setForecasts] = useState<Record<string, any>>({});
  const [alerts, setAlerts] = useState<any[]>([]);

  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
    let socket: WebSocket | null = null;

    function connectWs() {
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        setWsConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { type, data } = payload;

          if (type === "TELEMETRY_RAW") {
            setTelemetry((prev) => ({ ...prev, [data.station_id || data.device_id]: data }));
          } else if (type === "AI_FORECAST") {
            setForecasts((prev) => ({ ...prev, [data.station_id || data.device_id]: data }));
          } else if (type === "ALERT_EVENT") {
            setAlerts((prev) => [data, ...prev.slice(0, 9)]);
          }
        } catch (e) {
          console.error("WS Parse error", e);
        }
      };

      socket.onclose = () => {
        setWsConnected(false);
        setTimeout(connectWs, 3000);
      };
    }

    connectWs();
    return () => {
      if (socket) socket.close();
    };
  }, []);

  const telemetryList = Object.values(telemetry);
  const forecastList = Object.values(forecasts);

  return (
    <div className="min-h-screen bg-[#0B0F19] text-gray-100 p-6">
      {/* Top Header Navigation */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center bg-[#111827] p-4 rounded-xl border border-gray-800 mb-6 gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-lg">
            <Cpu className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wide text-white">SMURF CONTROL ROOM PLATFORM</h1>
            <p className="text-xs text-gray-400">Enterprise Real-Time IoT & Multi-Agent AI System</p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${wsConnected ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border-rose-500/30'}`}>
            <Radio className="w-3.5 h-3.5" />
            <span>{wsConnected ? "REDPANDA WEBSOCKET ACTIVE" : "DISCONNECTED"}</span>
          </div>
          <div className="bg-gray-800 px-3 py-1.5 rounded-full text-gray-300 border border-gray-700">
            Active Nodes: {telemetryList.length}
          </div>
        </div>
      </header>

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Live IoT Telemetry Nodes */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-[#111827] rounded-xl border border-gray-800 p-5">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-sm font-semibold tracking-wider text-gray-300 uppercase flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Live IoT Telemetry Nodes (`topic_raw`)
              </h2>
              <span className="text-xs text-gray-500 font-mono">2s Stream Update</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {telemetryList.length === 0 ? (
                <div className="col-span-2 text-center py-12 text-gray-500 text-sm font-mono border border-dashed border-gray-800 rounded-lg">
                  Waiting for incoming IoT stream records...
                </div>
              ) : (
                telemetryList.map((item: any, idx) => (
                  <div key={idx} className="bg-gray-900/60 p-4 rounded-lg border border-gray-800 hover:border-gray-700 transition">
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-mono text-sm font-bold text-emerald-400">{item.station_id || item.device_id}</span>
                      <span className="text-[10px] bg-gray-800 text-gray-400 px-2 py-0.5 rounded font-mono">{item.protocol || "MQTT"}</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs font-mono mt-3">
                      <div className="bg-gray-950 p-2 rounded">
                        <span className="text-gray-500 block text-[10px]">TEMP</span>
                        <span className="text-white font-bold">{item.temp ?? "--"}°C</span>
                      </div>
                      <div className="bg-gray-950 p-2 rounded">
                        <span className="text-gray-500 block text-[10px]">HUMIDITY</span>
                        <span className="text-white font-bold">{item.humidity ?? "--"}%</span>
                      </div>
                      <div className="bg-gray-950 p-2 rounded">
                        <span className="text-gray-500 block text-[10px]">PRESSURE</span>
                        <span className="text-white font-bold">{item.pressure ?? "--"} hPa</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: AI Forecasts & Action Cards */}
        <div className="space-y-6">
          <div className="bg-[#111827] rounded-xl border border-gray-800 p-5">
            <h2 className="text-sm font-semibold tracking-wider text-gray-300 uppercase flex items-center gap-2 mb-4">
              <Zap className="w-4 h-4 text-amber-400" />
              Multi-Agent AI Forecasts (`topic_forecasts`)
            </h2>

            <div className="space-y-4">
              {forecastList.length === 0 ? (
                <div className="text-center py-12 text-gray-500 text-sm font-mono border border-dashed border-gray-800 rounded-lg">
                  No AI forecasts generated yet.
                </div>
              ) : (
                forecastList.map((fc: any, idx) => (
                  <div key={idx} className="bg-gray-900/80 p-4 rounded-lg border border-amber-500/30">
                    <div className="flex justify-between items-center mb-2">
                      <span className="font-mono text-xs font-bold text-amber-400">{fc.station_id}</span>
                      <span className="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded font-mono font-bold">
                        Risk: {fc.risk_score}/100 ({fc.risk_level})
                      </span>
                    </div>

                    <h3 className="text-sm font-semibold text-white mb-2">{fc.weather_condition}</h3>
                    <p className="text-xs text-gray-300 leading-relaxed mb-3">{fc.synoptic_analysis}</p>

                    {fc.smart_operational_decisions && (
                      <div className="space-y-1.5">
                        <span className="text-[10px] text-gray-400 font-mono uppercase tracking-wider block">Smart Operational Decisions:</span>
                        {fc.smart_operational_decisions.map((dec: string, dIdx: number) => (
                          <div key={dIdx} className="flex items-center gap-2 text-xs bg-emerald-500/10 text-emerald-300 p-2 rounded border border-emerald-500/20">
                            <CheckCircle className="w-3.5 h-3.5 shrink-0" />
                            <span>{dec}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
