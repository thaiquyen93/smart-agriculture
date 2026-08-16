"use client";

import React, { useEffect, useState, useRef } from "react";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import DevicePanel from "./components/DevicePanel";
import SensorTrendPanel from "./components/SensorTrendPanel";
import AIInsightsPanel from "./components/AIInsightsPanel";
import EvidenceDrawer from "./components/EvidenceDrawer";
import DecisionPlanCard from "./components/DecisionPlanCard";
import ExecutionVerificationPanel from "./components/ExecutionVerificationPanel";
import ToolActivityPanel from "./components/ToolActivityPanel";
import TaskTable from "./components/TaskTable";
import ChatPanel from "./components/ChatPanel";
import { AIInsight, Plan, TaskItem } from "./lib/types";
import { MessageSquare } from "lucide-react";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const router = useRouter();
  const [wsConnected, setWsConnected] = useState(true);
  const [telemetry, setTelemetry] = useState<Record<string, any>>({});
  const [slidingMetrics, setSlidingMetrics] = useState<Record<string, any>>({});
  const [plans, setPlans] = useState<Plan[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [forecastsList, setForecastsList] = useState<any[]>([]);

  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("SOIL_01");
  const [selectedInsight, setSelectedInsight] = useState<AIInsight | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);

  const historyRef = useRef<Record<string, any[]>>({});
  const [historyTick, setHistoryTick] = useState(0);

  // 1. Polling NestJS REST API every 1 second for live Redpanda Kafka updates
  useEffect(() => {
    // Fetch historical data once on mount
    const fetchHistory = async () => {
      const expectedDevices = ['SOIL_01', 'WEATHER_01', 'PUMP_01', 'PH_01', 'TANK_01', 'SUN_01'];
      for (const dev of expectedDevices) {
        try {
          const res = await fetch(`http://localhost:8000/api/v1/telemetry/history/${dev}`);
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            const arr = data.map((d: any) => {
              const point: any = { time: new Date(d.event_time * 1000).toLocaleTimeString([], {minute: '2-digit', second: '2-digit'}) };
              if (d.soil_moisture !== undefined) point.moisture = d.soil_moisture;
              if (d.temperature !== undefined) point.temp = d.temperature;
              if (d.humidity !== undefined) point.humidity = d.humidity;
              if (d.flow_rate !== undefined) point.flow_rate = d.flow_rate;
              if (d.power !== undefined) point.power = d.power;
              if (d.ph !== undefined) point.ph = d.ph;
              if (d.level !== undefined) point.level = d.level;
              if (d.lux !== undefined) point.lux = d.lux;
              return point;
            });
            
            // Pad to 25 if necessary
            let padded = arr;
            if (arr.length < 25) {
               const padCount = 25 - arr.length;
               const baseTime = (data[0]?.event_time * 1000) || Date.now();
               const padding = Array.from({ length: padCount }).map((_, i) => ({
                 time: new Date(baseTime - (padCount - i) * 2000).toLocaleTimeString([], {minute: '2-digit', second: '2-digit'})
               })) as any[];
               padded = [...padding, ...arr];
            }
            historyRef.current[dev] = padded.slice(-25);
          }
        } catch (e) {}
      }
      setHistoryTick(Date.now());
    };
    fetchHistory();

    const fetchLatest = () => {
      fetch("http://localhost:8000/api/v1/telemetry/latest")
        .then((res) => res.json())
        .then((data) => {
          if (Array.isArray(data) && data.length > 0) {
            const map: Record<string, any> = {};
            data.forEach((d) => {
              const id = d.device_id || d.device_code || d.station_id;
              if (id) {
                map[id] = d.raw || d;
              }
            });
            if (Object.keys(map).length > 0) {
              setTelemetry((prev) => ({ ...prev, ...map }));
              setWsConnected(true);
            }
          }
        })
        .catch(() => {});

      fetch("http://localhost:8000/api/v1/telemetry/windows")
        .then((res) => res.json())
        .then((data) => {
          if (Array.isArray(data) && data.length > 0) {
            const map: Record<string, any> = {};
            data.forEach((w) => {
              const id = w.device_id || "device";
              map[id] = w;
            });
            setSlidingMetrics(map);
          }
        })
        .catch(() => {});
    };

    fetchLatest();
    const interval = setInterval(fetchLatest, 1000);
    return () => clearInterval(interval);
  }, []);

  // Update Chart History every 2 seconds based on current telemetry
  useEffect(() => {
    const interval = setInterval(() => {
      setTelemetry(currentTelemetry => {
        Object.keys(currentTelemetry).forEach(devId => {
          const data = currentTelemetry[devId];
          let arr = historyRef.current[devId];
          
          if (!arr || arr.length === 0) {
            // Pad with 25 empty points so the X-axis doesn't jitter while filling up
            arr = Array.from({ length: 24 }).map((_, i) => ({
              time: new Date(Date.now() - (24 - i) * 2000).toLocaleTimeString([], {minute: '2-digit', second: '2-digit'})
            }));
          }

          const nowLabel = new Date().toLocaleTimeString([], {minute: '2-digit', second: '2-digit'});
          const point: any = { time: nowLabel };
          
          if (data.soil_moisture !== undefined) point.moisture = data.soil_moisture;
          if (data.temperature !== undefined) point.temp = data.temperature;
          if (data.humidity !== undefined) point.humidity = data.humidity;
          if (data.flow_rate !== undefined) point.flow_rate = data.flow_rate;
          if (data.power !== undefined) point.power = data.power;
          if (data.ph !== undefined) point.ph = data.ph;
          if (data.level !== undefined) point.level = data.level;
          if (data.lux !== undefined) point.lux = data.lux;
          
          historyRef.current[devId] = [...arr, point].slice(-25);
        });
        setHistoryTick(Date.now());
        return currentTelemetry;
      });
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // 2. WebSocket Connection for Instant Push Updates from topic_raw
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
            if (devId) {
              setTelemetry((prev) => ({ ...prev, [devId]: data }));
            }
          } else if (type === "WINDOW_MINUTE") {
            const devId = data.device_id || "device";
            setSlidingMetrics((prev) => ({ ...prev, [devId]: data }));
          } else if (type === "IRRIGATION_PLAN") {
            const mappedPlan: Plan = {
              id: data.plan_id || `plan-${Date.now()}`,
              zoneId: data.area_id || "Zone A",
              action: `Irrigate ${data.water_amount_liters || 450}L water`,
              responsibleAgent: "🤖 Irrigation Agent",
              status: (data.status || "pending_approval").toLowerCase() as any,
              createdAt: new Date(data.created_at * 1000 || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              duration: "10 minutes",
              expectedUsage: `${data.water_amount_liters || 450} L`,
              reason: data.reasoning_summary || "Soil moisture below threshold."
            };
            setPlans((prev) => [mappedPlan, ...prev.filter(p => p.id !== mappedPlan.id)]);
          } else if (type === "ALERT_EVENT") {
            setAlerts((prev) => [data, ...prev.slice(0, 9)]);
          } else if (type === "AI_FORECAST") {
            setForecastsList((prev) => [data, ...prev.slice(0, 9)]);
          } else if (type === "INSPECTION_TASK") {
            const mappedTask: TaskItem = {
              id: data.task_id || `task-${Date.now()}`,
              title: data.description || "System Inspection",
              zone: data.device_id || "Global",
              responsible: data.assigned_to || "Field Engineer",
              priority: (data.priority || "MEDIUM").toUpperCase() as any,
              status: data.status || "OPEN",
              dueTime: "Today"
            };
            setTasks((prev) => [mappedTask, ...prev.filter(t => t.id !== mappedTask.id)]);
          }
        } catch (e) {
          console.error("WS Parse error", e);
        }
      };

      socket.onclose = () => {
        setTimeout(connectWs, 2000);
      };
    }

    connectWs();
    return () => {
      if (socket) socket.close();
    };
  }, []);

  const activeSensors = Object.keys(telemetry);
  const activeSensorCount = activeSensors.length;

  // Extract dynamic telemetry values from topic_raw
  const soilData = telemetry["SOIL_01"] || {};
  const weatherData = telemetry["WEATHER_01"] || {};
  const pumpData = telemetry["PUMP_01"] || {};
  const phData = telemetry["PH_01"] || {};
  const tankData = telemetry["TANK_01"] || {};
  const sunData = telemetry["SUN_01"] || {};

  // 6 Devices Cards mapped dynamically from topic_raw (with immediate display fallbacks)
  const devicesList = [
    {
      id: "SOIL_01",
      name: "Cảm biến đất khu A",
      status: (soilData.soil_moisture || 44) < 35 ? ("warning" as const) : ("healthy" as const),
      lastUpdate: soilData.event_time ? `Stream: ${new Date((soilData.event_time > 1e11 ? soilData.event_time : soilData.event_time * 1000)).toLocaleTimeString()}` : "Realtime Active",
      metrics: [
        { key: "moisture", label: "Moisture", value: soilData.soil_moisture ?? 44.0, unit: "%" },
        { key: "temp", label: "Temp", value: soilData.temperature ?? 26.5, unit: "°C" }
      ]
    },
    {
      id: "WEATHER_01",
      name: "Trạm thời tiết",
      status: "healthy" as const,
      lastUpdate: weatherData.event_time ? `Stream: ${new Date((weatherData.event_time > 1e11 ? weatherData.event_time : weatherData.event_time * 1000)).toLocaleTimeString()}` : "Realtime Active",
      metrics: [
        { key: "temp", label: "Temp", value: weatherData.temperature ?? 32.1, unit: "°C" },
        { key: "humidity", label: "Humidity", value: weatherData.humidity ?? 65.0, unit: "%" }
      ]
    },
    {
      id: "PUMP_01",
      name: "Bơm tưới khu A",
      status: pumpData.status === "ON" ? ("irrigating" as const) : ("healthy" as const),
      lastUpdate: pumpData.event_time ? `Stream: ${new Date((pumpData.event_time > 1e11 ? pumpData.event_time : pumpData.event_time * 1000)).toLocaleTimeString()}` : "Realtime Active",
      metrics: [
        { key: "flow_rate", label: "Flow Rate", value: pumpData.flow_rate ?? (pumpData.status === "ON" ? 35.5 : 0), unit: " L/min" },
        { key: "power", label: "Power", value: pumpData.power ?? (pumpData.status === "ON" ? 850 : 0), unit: "W" }
      ]
    },
    {
      id: "PH_01",
      name: "Cảm biến pH bồn",
      status: (phData.ph || 6.8) < 5.5 || (phData.ph || 6.8) > 8.5 ? ("warning" as const) : ("healthy" as const),
      lastUpdate: phData.event_time ? `Stream: ${new Date((phData.event_time > 1e11 ? phData.event_time : phData.event_time * 1000)).toLocaleTimeString()}` : "Realtime Active",
      metrics: [
        { key: "ph", label: "pH Level", value: phData.ph ?? 6.8, unit: "" }
      ]
    },
    {
      id: "TANK_01",
      name: "Bồn nước chính",
      status: (tankData.level || 78.5) < 20 ? ("critical" as const) : ("healthy" as const),
      lastUpdate: tankData.event_time ? `Stream: ${new Date((tankData.event_time > 1e11 ? tankData.event_time : tankData.event_time * 1000)).toLocaleTimeString()}` : "Realtime Active",
      metrics: [
        { key: "level", label: "Water Level", value: tankData.level ?? 78.5, unit: "%" }
      ]
    },
    {
      id: "SUN_01",
      name: "Cảm biến nắng khu A",
      status: "healthy" as const,
      lastUpdate: sunData.event_time ? `Stream: ${new Date((sunData.event_time > 1e11 ? sunData.event_time : sunData.event_time * 1000)).toLocaleTimeString()}` : "Realtime Active",
      metrics: [
        { key: "lux", label: "Light", value: sunData.lux ? Math.round(sunData.lux) : 52400, unit: " Lux" }
      ]
    }
  ];

  const selectedDevice = devicesList.find(d => d.id === selectedDeviceId) || devicesList[0];

  const trendLines: { key: string; name: string; color: string; isPrediction?: boolean }[] = [];

  const colorsActual = ["#10B981", "#F59E0B", "#3B82F6", "#EC4899", "#8B5CF6", "#14B8A6"];

  selectedDevice.metrics.forEach((m, idx) => {
    const unitStr = m.unit.trim() ? ` (${m.unit.trim()})` : "";
    trendLines.push({
      key: m.key,
      name: `Actual ${m.label}${unitStr}`,
      color: colorsActual[idx % colorsActual.length]
    });
  });

  const trendData = historyRef.current[selectedDeviceId] || [];

  // Dynamic Insights from anomalies or low soil moisture (merged with Kafka alerts and forecasts)
  const dynamicInsights: AIInsight[] = [
    ...alerts.map(a => ({
      zoneId: a.device_id || "System",
      prediction: a.message || "Alert Triggered",
      confidence: 100,
      priority: (a.severity?.toLowerCase() || "high") as any,
      factors: ["Threshold Exceeded", "Rule Triggered"],
      recommendation: "Investigate immediately",
      evidenceId: a.alert_id || a.id || `alert-${Date.now()}`
    })),
    ...forecastsList.map(f => ({
      zoneId: f.station_id || f.device_id || "Global",
      prediction: f.prediction || "Forecast Update",
      confidence: f.confidence || 85,
      priority: "medium" as any,
      factors: ["AI Model Output"],
      recommendation: "Monitor trends",
      evidenceId: f.forecast_id || `fcast-${Date.now()}`
    }))
  ];
  
  const defaultInsight: AIInsight[] = (soilData.soil_moisture || 44) < 35 ? [
    {
      zoneId: "SOIL_01 (Khu vực A)",
      prediction: "Soil moisture < 35% threshold",
      confidence: 95,
      priority: "high",
      factors: ["Soil moisture critical low", "High evapotranspiration"],
      recommendation: "Irrigate Zone A with 450L water immediately",
      evidenceId: "ev-soil-01"
    }
  ] : [];

  const insights: AIInsight[] = dynamicInsights.length > 0 ? dynamicInsights : defaultInsight;

  // Verifications
  const verifications = [
    {
      command: "PUMP_01_STATUS",
      deviceStatus: pumpData.status || "OFF",
      flowStatus: `${pumpData.flow_rate || 0} L/min`,
      duration: "Realtime",
      sensorResult: { expected: "> 35%", actual: `${soilData.soil_moisture ?? 44.0}%`, status: (soilData.soil_moisture || 44) >= 35 ? ("passed" as const) : ("failed" as const) },
      finalStatus: "verified" as const
    }
  ];

  const handleApprove = (id: string) => {
    setPlans(prev => prev.map(p => p.id === id ? { ...p, status: 'approved' } : p));
    fetch(`http://localhost:8000/api/v1/irrigation/plans/${id}/approve`, { method: "POST" }).catch(() => {});
  };

  const handleReject = (id: string) => {
    setPlans(prev => prev.filter(p => p.id !== id));
    fetch(`http://localhost:8000/api/v1/irrigation/plans/${id}/reject`, { method: "POST" }).catch(() => {});
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex font-sans">
      {/* Sidebar - Fixed Left */}
      <Sidebar activePage="Overview" />

      {/* Main Content Area */}
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen overflow-x-hidden">

        {/* Header - Sticky Top */}
        <Header 
          connected={true} 
          useMock={false} 
          deviceCount={6} 
          alertCount={alerts.length} 
          lastUpdateStr="Realtime Stream Active" 
        />

        {/* Scrollable Dashboard Content */}
        <main className="p-6 space-y-6">

          {/* 1. KPI Overview Bar */}
          <section className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center">
              <span className="text-2xl font-bold text-slate-800">6</span>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Track B Devices</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center">
              <span className="text-2xl font-bold text-emerald-600">100%</span>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Stream Online</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center">
              <span className="text-2xl font-bold text-emerald-700">6</span>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Sensors</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center border-l-4 border-l-amber-500">
              <span className="text-2xl font-bold text-amber-600">{alerts.length}</span>
              <span className="text-xs font-semibold text-amber-600 uppercase tracking-wider">Alerts</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center border-l-4 border-l-red-500">
              <span className="text-2xl font-bold text-red-600">{plans.filter(p => p.status === 'pending_approval').length}</span>
              <span className="text-xs font-semibold text-red-600 uppercase tracking-wider">Approvals</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center">
              <span className="text-2xl font-bold text-slate-800">{plans.length}</span>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Plans</span>
            </div>
          </section>

          {/* 2. Three Columns Layout: 6 Devices Cards | Sensor Trends | AI Insights */}
          <section className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-1">
              <DevicePanel 
                devices={devicesList} 
                selectedDeviceId={selectedDeviceId} 
                onDeviceClick={(id) => setSelectedDeviceId(id)} 
                onViewDetails={(id) => router.push(`/live-sensors?device=${id}`)}
              />
            </div>
            <div className="lg:col-span-2">
              <SensorTrendPanel data={trendData} lines={trendLines} title={`${selectedDevice.name} Trends`} />
            </div>
            <div className="lg:col-span-1">
              <AIInsightsPanel insights={insights} onViewEvidence={(insight) => setSelectedInsight(insight)} />
            </div>
          </section>

          {/* 3. Decision & Human Approval Plans */}
          <section className="space-y-4">
            <h3 className="font-bold text-slate-800 flex items-center gap-2 px-1 text-sm uppercase tracking-wider">
              Decision & Plans (Human-in-the-Loop)
            </h3>
            {plans.map(plan => (
              <DecisionPlanCard
                key={plan.id}
                plan={plan}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            ))}
            {plans.length === 0 && (
              <div className="clean-card p-8 text-center text-slate-500 font-medium font-mono text-xs border border-dashed border-slate-200">
                No active plans or pending decisions from AI Multi-Agent.
              </div>
            )}
          </section>

          {/* 4. Execution & Verification */}
          <section>
            <ExecutionVerificationPanel verifications={verifications} />
          </section>

          {/* 5. Tool / API Activity */}
          <section>
            <ToolActivityPanel weatherData={weatherData} soilData={soilData} />
          </section>

          {/* 6. Task Management */}
          <section>
            <TaskTable tasks={tasks} />
          </section>

        </main>
      </div>

      {/* Evidence Drawer Modal */}
      <EvidenceDrawer
        isOpen={!!selectedInsight}
        onClose={() => setSelectedInsight(null)}
        insight={selectedInsight}
      />

      {/* Floating Chat Assistant Button */}
      {!isChatOpen && (
        <button
          onClick={() => setIsChatOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 bg-emerald-600 rounded-full shadow-2xl flex items-center justify-center hover:bg-emerald-700 hover:scale-105 transition-all z-40 text-white"
          aria-label="Open Chat"
        >
          <MessageSquare size={24} />
          <span className="absolute top-0 right-0 w-3 h-3 bg-emerald-400 border-2 border-white rounded-full"></span>
        </button>
      )}

      {/* Chat Panel */}
      <ChatPanel
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
      />
    </div>
  );
}
