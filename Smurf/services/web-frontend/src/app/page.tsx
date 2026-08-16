"use client";

import React, { useEffect, useState } from "react";
import { 
  Activity, ShieldAlert, Cpu, Radio, Zap, CheckCircle, XCircle, 
  Droplets, Sun, Wind, Gauge, AlertTriangle, Layers, UserCheck, Wrench
} from "lucide-react";

export default function ControlRoomPage() {
  const [wsConnected, setWsConnected] = useState(false);
  const [telemetry, setTelemetry] = useState<Record<string, any>>({});
  const [slidingMetrics, setSlidingMetrics] = useState<Record<string, any>>({});
  const [irrigationPlans, setIrrigationPlans] = useState<any[]>([]);
  const [inspectionTasks, setInspectionTasks] = useState<any[]>([]);
  const [agentLogs, setAgentLogs] = useState<any[]>([]);

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
            const devId = data.device_id || data.device_code || data.station_id;
            setTelemetry((prev) => ({ ...prev, [devId]: data }));
          } else if (type === "WINDOW_MINUTE") {
            if (data.window_type === "SLIDING_30M" || data.window_type === "TUMBLING_1M") {
              setSlidingMetrics((prev) => ({ ...prev, [data.device_id]: data }));
            }
          } else if (type === "IRRIGATION_PLAN") {
            setIrrigationPlans((prev) => [data, ...prev.filter(p => p.plan_id !== data.plan_id)]);
          } else if (type === "INSPECTION_TASK") {
            setInspectionTasks((prev) => [data, ...prev.filter(t => t.task_id !== data.task_id)]);
          } else if (type === "AGENT_LOG") {
            setAgentLogs((prev) => [data, ...prev.slice(0, 19)]);
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

  const sensorKeys = ["SOIL_01", "WEATHER_01", "PUMP_01", "PH_01", "TANK_01", "SUN_01"];

  const handleApprovePlan = (planId: string) => {
    setIrrigationPlans((prev) =>
      prev.map((p) => (p.plan_id === planId ? { ...p, status: "APPROVED" } : p))
    );
  };

  const handleRejectPlan = (planId: string) => {
    setIrrigationPlans((prev) =>
      prev.map((p) => (p.plan_id === planId ? { ...p, status: "REJECTED" } : p))
    );
  };

  return (
    <div className="min-h-screen bg-[#090D16] text-gray-100 p-4 md:p-6 font-sans">
      {/* Top Header Navigation */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center bg-[#111827] p-4 rounded-xl border border-gray-800 mb-6 gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-emerald-500/20 text-emerald-400 rounded-lg border border-emerald-500/30">
            <Cpu className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wide text-white flex items-center gap-2">
              SMURF SMART AGRICULTURE CONTROL ROOM
              <span className="text-xs font-mono bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded border border-emerald-500/30">TRACK B</span>
            </h1>
            <p className="text-xs text-gray-400">Multi-Agent Farm Operations & Real-Time Redpanda Stream Processing Engine</p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${wsConnected ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border-rose-500/30'}`}>
            <Radio className="w-3.5 h-3.5" />
            <span>{wsConnected ? "REDPANDA KAFKA WS ONLINE" : "WS RECONNECTING"}</span>
          </div>
          <div className="bg-gray-800 px-3 py-1.5 rounded-full text-gray-300 border border-gray-700">
            Sensors: {Object.keys(telemetry).length}/6 Active
          </div>
        </div>
      </header>

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Columns: Live Sensors & 30-Min Sliding Metrics */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* SECTION 1: 6 Sensor Cards */}
          <div className="bg-[#111827] rounded-xl border border-gray-800 p-5 shadow-lg">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-sm font-semibold tracking-wider text-gray-200 uppercase flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                Live IoT Telemetry Sensors (`topic_raw`)
              </h2>
              <span className="text-xs text-emerald-400 font-mono flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" /> Realtime 3s Stream
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {sensorKeys.map((code) => {
                const data = telemetry[code] || {};
                const hasData = !!telemetry[code];

                return (
                  <div key={code} className={`p-4 rounded-xl border transition ${hasData ? 'bg-gray-900/80 border-gray-800 hover:border-gray-700' : 'bg-gray-950/40 border-gray-900 opacity-60'}`}>
                    <div className="flex justify-between items-center mb-3">
                      <span className="font-mono text-sm font-bold text-emerald-400">{code}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold ${hasData ? 'bg-emerald-500/20 text-emerald-300' : 'bg-gray-800 text-gray-500'}`}>
                        {hasData ? "ONLINE" : "WAITING"}
                      </span>
                    </div>

                    {/* Sensor Payload Value Display */}
                    {code === "SOIL_01" && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400 flex items-center gap-1"><Droplets className="w-3 h-3 text-cyan-400" /> Soil Moisture:</span>
                          <span className="text-white font-bold">{data.soil_moisture ?? "--"}%</span>
                        </div>
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400">Soil Temp:</span>
                          <span className="text-white">{data.temperature ?? "--"}°C</span>
                        </div>
                      </div>
                    )}

                    {code === "WEATHER_01" && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400 flex items-center gap-1"><Wind className="w-3 h-3 text-blue-400" /> Air Temp:</span>
                          <span className="text-white font-bold">{data.temperature ?? "--"}°C</span>
                        </div>
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400">Humidity:</span>
                          <span className="text-white">{data.humidity ?? "--"}%</span>
                        </div>
                      </div>
                    )}

                    {code === "PUMP_01" && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400 flex items-center gap-1"><Gauge className="w-3 h-3 text-amber-400" /> Pump Status:</span>
                          <span className={`font-bold ${data.status === 'ON' ? 'text-emerald-400' : 'text-gray-400'}`}>{data.status ?? "OFF"}</span>
                        </div>
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400">Flow / Power:</span>
                          <span className="text-white">{data.flow_rate ?? 0} L/m | {data.power ?? 0}W</span>
                        </div>
                      </div>
                    )}

                    {code === "PH_01" && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400">Tank pH Value:</span>
                          <span className="text-emerald-300 font-bold">{data.ph ?? "--"} pH</span>
                        </div>
                      </div>
                    )}

                    {code === "TANK_01" && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400 flex items-center gap-1"><Droplets className="w-3 h-3 text-blue-400" /> Tank Water Level:</span>
                          <span className="text-cyan-300 font-bold">{data.level ?? "--"}%</span>
                        </div>
                      </div>
                    )}

                    {code === "SUN_01" && (
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-gray-400 flex items-center gap-1"><Sun className="w-3 h-3 text-amber-300" /> Sunlight Lux:</span>
                          <span className="text-amber-200 font-bold">{data.lux ?? "--"} lx</span>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* SECTION 2: 10-Min Sliding Window Aggregation (topic_p) */}
          <div className="bg-[#111827] rounded-xl border border-gray-800 p-5 shadow-lg">
            <h2 className="text-sm font-semibold tracking-wider text-gray-200 uppercase flex items-center gap-2 mb-4">
              <Layers className="w-4 h-4 text-cyan-400" />
              10-Min Sliding Window Analytics (SLIDING_10M → topic_p)
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
              {Object.keys(slidingMetrics).length === 0 ? (
                <div className="col-span-2 text-center py-8 text-gray-500 border border-dashed border-gray-800 rounded-lg">
                  Accumulating 10-minute sliding window metrics from Redpanda Kafka...
                </div>
              ) : (
                Object.values(slidingMetrics).map((win: any, idx) => (
                  <div key={idx} className="bg-gray-900/60 p-4 rounded-xl border border-gray-800">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-cyan-400 font-bold">{win.device_id}</span>
                      <span className="bg-cyan-500/20 text-cyan-300 px-2 py-0.5 rounded text-[10px]">{win.window_type}</span>
                    </div>
                    <div className="space-y-1 text-gray-300">
                      <div>Count: <span className="text-white font-bold">{win.record_count} raw records</span></div>
                      {win.metrics && Object.entries(win.metrics).map(([k, v]: any) => (
                        <div key={k} className="flex justify-between text-[11px] border-t border-gray-800/60 pt-1">
                          <span className="text-gray-400">{k}:</span>
                          <span className="text-emerald-300 font-bold">{v}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Human Approval & Multi-Agent Reasoning Trace */}
        <div className="space-y-6">
          
          {/* SECTION 3: 1-Click Human Approval Panel */}
          <div className="bg-[#111827] rounded-xl border border-emerald-500/30 p-5 shadow-xl">
            <h2 className="text-sm font-semibold tracking-wider text-emerald-300 uppercase flex items-center gap-2 mb-4">
              <UserCheck className="w-4 h-4 text-emerald-400" />
              Farm Manager Approval Panel (Human-in-the-Loop)
            </h2>

            <div className="space-y-4">
              {irrigationPlans.length === 0 ? (
                <div className="text-center py-6 text-gray-500 text-xs font-mono border border-dashed border-gray-800 rounded-lg">
                  No active irrigation plans pending approval.
                </div>
              ) : (
                irrigationPlans.map((plan: any) => (
                  <div key={plan.plan_id} className="bg-gray-900/90 p-4 rounded-xl border border-gray-800 space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="font-mono text-xs font-bold text-emerald-400">{plan.plan_id}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${plan.status === 'APPROVED' ? 'bg-emerald-500/20 text-emerald-300' : plan.status === 'REJECTED' ? 'bg-rose-500/20 text-rose-300' : 'bg-amber-500/20 text-amber-300 animate-pulse'}`}>
                        {plan.status}
                      </span>
                    </div>

                    <div className="text-xs text-gray-300 font-mono space-y-1">
                      <div>Area: <span className="text-white font-bold">{plan.area_id}</span></div>
                      <div>Water Volume: <span className="text-cyan-300 font-bold">{plan.water_amount_liters} Liters</span> ({plan.suggested_time})</div>
                      <div className="text-gray-400 text-[11px] leading-relaxed bg-gray-950 p-2 rounded border border-gray-850 mt-2">
                        {plan.reasoning_summary}
                      </div>
                    </div>

                    {plan.status === "PENDING_APPROVAL" && (
                      <div className="flex gap-2 pt-1">
                        <button
                          onClick={() => handleApprovePlan(plan.plan_id)}
                          className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white py-1.5 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 shadow"
                        >
                          <CheckCircle className="w-3.5 h-3.5" /> Approve Plan
                        </button>
                        <button
                          onClick={() => handleRejectPlan(plan.plan_id)}
                          className="flex-1 bg-rose-600 hover:bg-rose-500 text-white py-1.5 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1.5 shadow"
                        >
                          <XCircle className="w-3.5 h-3.5" /> Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* SECTION 4: Inspection Tasks (Persona: Field Operator) */}
          <div className="bg-[#111827] rounded-xl border border-gray-800 p-5 shadow-lg">
            <h2 className="text-sm font-semibold tracking-wider text-amber-300 uppercase flex items-center gap-2 mb-4">
              <Wrench className="w-4 h-4 text-amber-400" />
              Field Inspection Tasks (`topic_inspection_tasks`)
            </h2>

            <div className="space-y-3 font-mono text-xs">
              {inspectionTasks.length === 0 ? (
                <div className="text-center py-6 text-gray-500 border border-dashed border-gray-800 rounded-lg">
                  No open field maintenance tickets.
                </div>
              ) : (
                inspectionTasks.map((t: any) => (
                  <div key={t.task_id} className="bg-gray-900 p-3 rounded-lg border border-amber-500/20">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold text-amber-400">{t.task_id}</span>
                      <span className="bg-emerald-500/20 text-emerald-300 text-[10px] px-2 py-0.5 rounded">VERIFIED</span>
                    </div>
                    <div className="text-gray-300">{t.description}</div>
                    <div className="text-gray-500 text-[10px] mt-1">Assigned: {t.assigned_to}</div>
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
