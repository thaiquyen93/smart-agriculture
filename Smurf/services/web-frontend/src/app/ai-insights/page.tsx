"use client";

import React, { useEffect, useState } from "react";
import Header from "../components/Header";
import Sidebar from "../components/Sidebar";
import AIInsightsPanel from "../components/AIInsightsPanel";
import EvidenceDrawer from "../components/EvidenceDrawer";
import { AIInsight } from "../lib/types";

export default function AIInsightsPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [forecastsList, setForecastsList] = useState<any[]>([]);
  const [selectedInsight, setSelectedInsight] = useState<AIInsight | null>(null);

  useEffect(() => {
    // Basic WS logic just for ALERTS and FORECASTS
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
    let socket: WebSocket | null = null;

    function connectWs() {
      socket = new WebSocket(wsUrl);

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { type, data } = payload;

          if (type === "ALERT_EVENT") {
            setAlerts((prev) => [data, ...prev.slice(0, 9)]);
          } else if (type === "AI_FORECAST") {
            setForecastsList((prev) => [data, ...prev.slice(0, 9)]);
          } else if (type === "AGENT_NOTIFICATION") {
            setAlerts((prev) => [{ ...data, source: "agent-core" }, ...prev.slice(0, 9)]);
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
  
  // Sort by date (in this case, they are prepended so [0] is the latest)
  // "chỉ hiện cái mới nhất thôi" -> take index 0
  const insightsToShow = dynamicInsights.length > 0 ? [dynamicInsights[0]] : [];

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex font-sans">
      <Sidebar activePage="AI Insights" />

      <div className="flex-1 md:ml-64 flex flex-col min-h-screen overflow-x-hidden">
        <Header 
          connected={true} 
          useMock={false} 
          deviceCount={6} 
          alertCount={alerts.length} 
          lastUpdateStr="Realtime Stream Active" 
        />

        <main className="p-6">
          <section className="max-w-4xl mx-auto mt-6">
            <h2 className="text-xl font-bold text-slate-800 mb-6">Latest AI Insight</h2>
            <div className="h-auto">
              <AIInsightsPanel insights={insightsToShow} onViewEvidence={(insight) => setSelectedInsight(insight)} />
            </div>
          </section>
        </main>
      </div>

      <EvidenceDrawer
        isOpen={!!selectedInsight}
        onClose={() => setSelectedInsight(null)}
        insight={selectedInsight}
      />
    </div>
  );
}
