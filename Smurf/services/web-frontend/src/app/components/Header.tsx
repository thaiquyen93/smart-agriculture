"use client";

import React from "react";
import { Bell, Search, Activity, WifiOff, AlertTriangle } from "lucide-react";

interface HeaderProps {
  connected: boolean;
  useMock: boolean;
  deviceCount: number;
  alertCount: number;
  lastUpdateStr?: string;
  isStale?: boolean;
}

export default function Header({ connected, useMock, deviceCount, alertCount, lastUpdateStr = "8 sec ago", isStale = false }: HeaderProps) {
  
  const getStatusColor = () => {
    if (!connected && !useMock) return "text-red-500 bg-red-50";
    if (isStale) return "text-amber-500 bg-amber-50";
    return "text-emerald-500 bg-emerald-50";
  };
  
  const getStatusIcon = () => {
    if (!connected && !useMock) return <WifiOff size={16} />;
    if (isStale) return <AlertTriangle size={16} />;
    return <Activity size={16} />;
  };

  const getStatusText = () => {
    if (!connected && !useMock) return "Offline";
    if (isStale) return "Data Stale";
    if (useMock) return "Demo Mode - Healthy";
    return "System Healthy";
  };

  return (
    <header className="h-[73px] bg-white border-b border-slate-200 flex items-center justify-between px-6 sticky top-0 z-30">
      {/* Left: Farm Info */}
      <div className="flex items-center gap-6">
        <div>
          <h2 className="text-xl font-bold text-slate-800 leading-tight">Farm A</h2>
          <div className="flex items-center gap-3 text-sm text-slate-500 font-medium">
            <span>24 Zones</span>
            <span className="w-1 h-1 rounded-full bg-slate-300"></span>
            <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-md ${getStatusColor()}`}>
              {getStatusIcon()}
              <span className="font-semibold">{getStatusText()}</span>
              {connected && !isStale && <span className="ml-1 text-[11px] opacity-80">98% Online</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Right: Actions & User */}
      <div className="flex items-center gap-6">
        {/* Freshness */}
        <div className="text-right flex flex-col items-end">
          <span className={`text-xs font-semibold ${isStale ? 'text-amber-600' : 'text-slate-400'}`}>
            {isStale ? "⚠ Data stale" : "Last updated"}
          </span>
          <span className={`text-sm font-mono ${isStale ? 'text-amber-700' : 'text-slate-600'}`}>
            {isStale ? `Last update ${lastUpdateStr}` : lastUpdateStr}
          </span>
        </div>

        <div className="h-8 w-px bg-slate-200"></div>

        {/* Icons */}
        <div className="flex items-center gap-2">
          <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-full transition-colors relative">
            <Search size={20} />
          </button>
          <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-full transition-colors relative">
            <Bell size={20} />
            {alertCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2.5 h-2.5 bg-red-500 border-2 border-white rounded-full"></span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}

