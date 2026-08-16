"use client";

import React, { useState } from "react";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import ZonePanel from "./components/ZonePanel";
import SensorTrendPanel from "./components/SensorTrendPanel";
import AIInsightsPanel from "./components/AIInsightsPanel";
import EvidenceDrawer from "./components/EvidenceDrawer";
import DecisionPlanCard from "./components/DecisionPlanCard";
import ExecutionVerificationPanel from "./components/ExecutionVerificationPanel";
import ToolActivityPanel from "./components/ToolActivityPanel";
import TaskTable from "./components/TaskTable";
import { AIInsight, Plan, Verification, TaskItem } from "./lib/types";

// --- MOCK DATA ---
const MOCK_ZONES = [
  { id: 'zone-a', name: 'Zone A', status: 'healthy' as const, soilMoisture: 42, temperature: 24, lastUpdate: '12 sec ago' },
  { id: 'zone-b', name: 'Zone B', status: 'warning' as const, soilMoisture: 23, temperature: 34.1, lastUpdate: '8 sec ago' },
  { id: 'zone-c', name: 'Zone C', status: 'healthy' as const, soilMoisture: 39, temperature: 26, lastUpdate: '15 sec ago' },
  { id: 'zone-d', name: 'Zone D', status: 'irrigating' as const, soilMoisture: 31, temperature: 28, lastUpdate: '2 sec ago' },
];

const MOCK_TREND_DATA = Array.from({ length: 24 }).map((_, i) => {
  const isFuture = i > 18;
  return {
    time: `${i}:00`,
    actual: isFuture ? null : 45 - Math.random() * 20,
    prediction: isFuture ? 25 - (i - 18) * 2 : null,
  };
});
MOCK_TREND_DATA[18].prediction = MOCK_TREND_DATA[18].actual; // connect line

const MOCK_INSIGHTS: AIInsight[] = [
  {
    zoneId: "Zone B",
    prediction: "19% in 4 hours",
    confidence: 91,
    priority: "high",
    factors: ["Soil moisture below threshold", "Temperature high"],
    recommendation: "Irrigate Zone B for 7 minutes",
    evidenceId: "ev-1"
  }
];

const INITIAL_PLANS: Plan[] = [
  {
    id: "plan-1",
    zoneId: "Zone B",
    action: "Irrigate for 7 minutes",
    responsibleAgent: "🤖 Irrigation Agent",
    status: "pending_approval",
    createdAt: "08:42",
    duration: "7 minutes",
    expectedUsage: "420 L",
    reason: "Predicted soil moisture will fall below the safe threshold within 4 hours."
  }
];

const MOCK_VERIFICATIONS = [
  {
    command: "PUMP_ON",
    deviceStatus: "ON",
    flowStatus: "42 L/min",
    duration: "7:02",
    sensorResult: { expected: "23%", actual: "27%", status: "passed" as const },
    finalStatus: "verified" as const
  },
  {
    command: "VALVE_CLOSE",
    deviceStatus: "UNKNOWN",
    flowStatus: "8 L/min",
    duration: "1:00",
    sensorResult: { expected: "Flow < 5", actual: "Flow = 8", status: "failed" as const },
    finalStatus: "failed" as const
  }
];

const MOCK_TASKS: TaskItem[] = [
  { id: "t1", title: "Irrigate Zone B", zone: "Zone B", responsible: "Irrigation Agent", priority: "HIGH", status: "Waiting Approval", dueTime: "08:45" },
  { id: "t2", title: "Inspect Pump A", zone: "Zone A", responsible: "Technician", priority: "MEDIUM", status: "In Progress", dueTime: "10:00" },
  { id: "t3", title: "Check Sensor S-021", zone: "Zone B", responsible: "Monitoring Agent", priority: "LOW", status: "Completed", dueTime: "09:30" },
];

export default function DashboardPage() {
  const [plans, setPlans] = useState<Plan[]>(INITIAL_PLANS);
  const [selectedInsight, setSelectedInsight] = useState<AIInsight | null>(null);

  const handleApprove = (id: string) => {
    setPlans(prev => prev.map(p => p.id === id ? { ...p, status: 'approved' } : p));
  };
  const handleReject = (id: string) => {
    setPlans(prev => prev.filter(p => p.id !== id));
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex">
      {/* Sidebar - Fixed Left */}
      <Sidebar activePage="Overview" />

      {/* Main Content Area */}
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen overflow-x-hidden">
        
        {/* Header - Sticky Top */}
        <Header 
          connected={true} 
          useMock={false} 
          deviceCount={24} 
          alertCount={3} 
          lastUpdateStr="8 sec ago" 
        />

        {/* Scrollable Dashboard Content */}
        <main className="p-6 space-y-6">
          
          {/* 1. KPI Overview Bar */}
          <section className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-slate-50">
              <span className="text-2xl font-bold text-slate-800">24</span>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Zones</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-slate-50">
              <span className="text-2xl font-bold text-emerald-600">98%</span>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Online</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-slate-50">
              <span className="text-2xl font-bold text-slate-800">18</span>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Sensors</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center border-l-4 border-l-amber-500 cursor-pointer hover:bg-amber-50">
              <span className="text-2xl font-bold text-amber-600">3</span>
              <span className="text-xs font-semibold text-amber-600 uppercase tracking-wider">Alerts</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center border-l-4 border-l-red-500 cursor-pointer hover:bg-red-50">
              <span className="text-2xl font-bold text-red-600">{plans.filter(p => p.status === 'pending_approval').length}</span>
              <span className="text-xs font-semibold text-red-600 uppercase tracking-wider">Approvals</span>
            </div>
            <div className="clean-card p-4 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-slate-50">
              <span className="text-2xl font-bold text-slate-800">4</span>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Plans</span>
            </div>
          </section>

          {/* 2. Three Columns Layout */}
          <section className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-1">
              <ZonePanel zones={MOCK_ZONES} onZoneClick={(id) => console.log('Clicked', id)} />
            </div>
            <div className="lg:col-span-2">
              <SensorTrendPanel data={MOCK_TREND_DATA} />
            </div>
            <div className="lg:col-span-1">
              <AIInsightsPanel insights={MOCK_INSIGHTS} onViewEvidence={(insight) => setSelectedInsight(insight)} />
            </div>
          </section>

          {/* 3. Decision & Plans */}
          <section className="space-y-4">
            <h3 className="font-bold text-slate-800 flex items-center gap-2 px-1">Decision & Plans</h3>
            {plans.map(plan => (
              <DecisionPlanCard 
                key={plan.id} 
                plan={plan} 
                onApprove={handleApprove} 
                onReject={handleReject} 
              />
            ))}
            {plans.length === 0 && (
              <div className="clean-card p-8 text-center text-slate-500 font-medium">
                No active plans or pending decisions.
              </div>
            )}
          </section>

          {/* 4. Execution & Verification */}
          <section>
            <ExecutionVerificationPanel verifications={MOCK_VERIFICATIONS} />
          </section>

          {/* 5. Tool / API Activity */}
          <section>
            <ToolActivityPanel />
          </section>

          {/* 6. Task Management */}
          <section>
            <TaskTable tasks={MOCK_TASKS} />
          </section>

        </main>
      </div>

      {/* Evidence Drawer Modal */}
      <EvidenceDrawer 
        isOpen={!!selectedInsight} 
        onClose={() => setSelectedInsight(null)} 
        insight={selectedInsight} 
      />
    </div>
  );
}

