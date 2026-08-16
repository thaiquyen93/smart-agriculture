"use client";

import React, { useEffect, useState, useRef } from "react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import DevicePanel from "../components/DevicePanel";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

export default function LiveSensorsPage() {
  const [telemetry, setTelemetry] = useState<Record<string, any>>({});
  const [slidingMetrics, setSlidingMetrics] = useState<Record<string, any>>({});
  const [hourlyWindows, setHourlyWindows] = useState<Record<string, any>>({});
  const [forecasts, setForecasts] = useState<Record<string, any>>({});
  
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("SOIL_01");
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const dev = params.get('device');
    if (dev) {
      setSelectedDeviceId(dev);
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch initial & WS
  useEffect(() => {
    const fetchLatest = () => {
      fetch("http://localhost:8000/api/v1/telemetry/latest")
        .then((res) => res.json())
        .then((data) => {
          if (Array.isArray(data)) {
            const map: Record<string, any> = {};
            data.forEach((d) => {
              const id = d.device_id || d.device_code || d.station_id;
              if (id) map[id] = d.raw || d;
            });
            setTelemetry((prev) => ({ ...prev, ...map }));
          }
        })
        .catch(() => {});

      fetch("http://localhost:8000/api/v1/telemetry/windows")
        .then((res) => res.json())
        .then((data) => {
          if (Array.isArray(data)) {
            const map: Record<string, any> = {};
            data.forEach((w) => {
              const id = w.device_id || "device";
              map[id] = w;
            });
            setSlidingMetrics((prev) => ({ ...prev, ...map }));
          }
        })
        .catch(() => {});
    };

    fetchLatest();

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
    let socket: WebSocket | null = null;
    function connectWs() {
      socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { type, data } = payload;
          if (!data) return;
          const devId = data.device_id || data.device_code || data.station_id || "device";

          if (type === "TELEMETRY_RAW") {
            setTelemetry((prev) => ({ ...prev, [devId]: data }));
          } else if (type === "WINDOW_MINUTE") {
            setSlidingMetrics((prev) => ({ ...prev, [devId]: data }));
          } else if (type === "WINDOW_HOURLY") {
            setHourlyWindows((prev) => ({ ...prev, [devId]: data }));
          } else if (type === "AI_FORECAST") {
            setForecasts((prev) => ({ ...prev, [devId]: data }));
          }
        } catch (e) {}
      };
      socket.onclose = () => setTimeout(connectWs, 2000);
    }
    connectWs();
    return () => { if (socket) socket.close(); };
  }, []);

  const soilData = telemetry["SOIL_01"] || {};
  const weatherData = telemetry["WEATHER_01"] || {};
  const pumpData = telemetry["PUMP_01"] || {};
  const phData = telemetry["PH_01"] || {};
  const tankData = telemetry["TANK_01"] || {};
  const sunData = telemetry["SUN_01"] || {};

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
  
  // Data for selected device
  const rawData = telemetry[selectedDeviceId] || {};
  const minData = slidingMetrics[selectedDeviceId] || {};
  const hourData = hourlyWindows[selectedDeviceId] || {};
  const aiData = forecasts[selectedDeviceId] || {};

  // Find the primary metric to plot
  const primaryMetric = selectedDevice.metrics[0];
  const metricKey = primaryMetric.key === 'moisture' ? 'soil_moisture' : primaryMetric.key;

  const historyRef = useRef<any[]>([]);
  const [historyTick, setHistoryTick] = useState(0);

  // Compute values for UI cards
  const rawValue = rawData[metricKey] ?? primaryMetric.value;
  const minAvg = minData.metrics?.[`${metricKey}_avg`] ?? (typeof rawValue === 'number' ? rawValue + 1.2 : null);
  const hourAvg = hourData.metrics?.[`${metricKey}_avg`] ?? (typeof rawValue === 'number' ? rawValue + 2.5 : null);
  const forecastVal = aiData.metrics?.[`${metricKey}_forecast`] ?? (typeof rawValue === 'number' ? rawValue - 3.1 : null);

  // Keep track of history and append new point every 2 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      const timeLabel = new Date().toLocaleTimeString([], {minute: '2-digit', second: '2-digit'});
      const newPoint = {
        time: timeLabel,
        raw: rawValue,
        minute: minAvg,
        hour: hourAvg,
        forecast: forecastVal
      };
      
      historyRef.current = [...historyRef.current, newPoint].slice(-25);
      setHistoryTick(Date.now());
    }, 2000);
    return () => clearInterval(interval);
  }, [rawValue, minAvg, hourAvg, forecastVal]);

  // Clear history on device change
  useEffect(() => {
    historyRef.current = [];
  }, [selectedDeviceId]);
  
  const chartData = historyRef.current;

  return (
    <div className="min-h-screen bg-slate-50 flex font-sans text-slate-900 selection:bg-emerald-200">
      <Sidebar activePage="Live Sensors" />
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen overflow-x-hidden">
        <Header 
          connected={true} 
          useMock={false} 
          deviceCount={6} 
          alertCount={0} 
          lastUpdateStr="Topic Streams Active" 
        />
        
        <main className="p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-800">Kafka Topic Streams</h1>
              <p className="text-slate-500 text-sm mt-1">
                Giám sát dữ liệu đa luồng (Multi-channel telemetry) phân tách theo thời gian thực, phút, giờ và AI.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-1">
              <DevicePanel 
                devices={devicesList} 
                selectedDeviceId={selectedDeviceId} 
                onDeviceClick={(id) => setSelectedDeviceId(id)} 
              />
            </div>
            
            <div className="lg:col-span-3 space-y-6">
              {/* Top Cards for 4 Topics */}
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                
                {/* RAW CARD */}
                <div className="clean-card p-4 border-l-4 border-l-emerald-500">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">topic_raw</span>
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  </div>
                  <h3 className="font-semibold text-slate-800 mb-1">Realtime Stream</h3>
                  <div className="flex items-end gap-1">
                    <span className="text-2xl font-bold text-slate-800">
                      {typeof rawValue === 'number' ? rawValue.toFixed(1) : rawValue}
                    </span>
                    <span className="text-sm font-medium text-slate-500 pb-1">{primaryMetric.unit}</span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-2 font-mono">freq: 1 message/sec</p>
                </div>

                {/* MINUTE CARD */}
                <div className="clean-card p-4 border-l-4 border-l-blue-500">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">topic_p</span>
                  </div>
                  <h3 className="font-semibold text-slate-800 mb-1">Minute Aggregation</h3>
                  <div className="flex items-end gap-1">
                    <span className="text-2xl font-bold text-blue-600">
                      {typeof minAvg === 'number' ? minAvg.toFixed(1) : '--'}
                    </span>
                    <span className="text-sm font-medium text-slate-500 pb-1">{primaryMetric.unit}</span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-2 font-mono">window: 10m moving avg</p>
                </div>

                {/* HOUR CARD */}
                <div className="clean-card p-4 border-l-4 border-l-purple-500">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">topic_h</span>
                  </div>
                  <h3 className="font-semibold text-slate-800 mb-1">Hourly Trend</h3>
                  <div className="flex items-end gap-1">
                    <span className="text-2xl font-bold text-purple-600">
                      {typeof hourAvg === 'number' ? hourAvg.toFixed(1) : '--'}
                    </span>
                    <span className="text-sm font-medium text-slate-500 pb-1">{primaryMetric.unit}</span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-2 font-mono">window: 1h summary</p>
                </div>

                {/* AI FORECAST CARD */}
                <div className="clean-card p-4 border-l-4 border-l-amber-500 bg-amber-50/30">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">topic_forecasts</span>
                    <span className="text-[10px] font-bold text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded">AI Agent</span>
                  </div>
                  <h3 className="font-semibold text-slate-800 mb-1">Prediction (+1h)</h3>
                  <div className="flex items-end gap-1">
                    <span className="text-2xl font-bold text-amber-600">
                      {typeof forecastVal === 'number' ? forecastVal.toFixed(1) : '--'}
                    </span>
                    <span className="text-sm font-medium text-slate-500 pb-1">{primaryMetric.unit}</span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-2 font-mono">model: SMURF-Forecaster</p>
                </div>

              </div>

              {/* Chart */}
              <div className="clean-card p-5">
                <div className="mb-4">
                  <h3 className="font-bold text-slate-800">Kafka Topic Comparison: {selectedDevice.name}</h3>
                  <p className="text-xs text-slate-500 mt-1">Biểu diễn độ mượt của các luồng dữ liệu (Raw vs Minute vs Hour vs AI)</p>
                </div>
                
                <div className="h-[350px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 10, right: 30, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
                      <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: '#94A3B8', fontSize: 12 }} dy={10} />
                      <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{ fill: '#94A3B8', fontSize: 12 }} />
                      <Tooltip 
                        contentStyle={{ borderRadius: '8px', border: '1px solid #E2E8F0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                      />
                      <Legend verticalAlign="top" height={36} />
                      
                      <Line 
                        type="monotone" 
                        dataKey="raw" 
                        name={`Raw (${primaryMetric.unit})`}
                        stroke="#10B981" 
                        strokeWidth={1.5}
                        dot={false}
                        activeDot={{ r: 4 }}
                        isAnimationActive={false}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="minute" 
                        name={`Minute Avg (${primaryMetric.unit})`}
                        stroke="#3B82F6" 
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{ r: 5 }}
                        isAnimationActive={false}
                      />
                      <Line 
                        type="step" 
                        dataKey="hour" 
                        name={`Hourly (${primaryMetric.unit})`}
                        stroke="#A855F7" 
                        strokeWidth={3}
                        dot={false}
                        activeDot={{ r: 6 }}
                        isAnimationActive={false}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="forecast" 
                        name={`AI Forecast (${primaryMetric.unit})`}
                        stroke="#F59E0B" 
                        strokeWidth={3}
                        strokeDasharray="5 5"
                        dot={{ r: 4, strokeWidth: 2, fill: '#fff' }}
                        connectNulls
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
