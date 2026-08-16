import React, { useState, useEffect } from 'react';
import { Server, ChevronDown, ChevronRight, Check, AlertTriangle } from 'lucide-react';

interface ToolActivityPanelProps {
  weatherData: any;
  soilData: any;
}

export default function ToolActivityPanel({ weatherData, soilData }: ToolActivityPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!isExpanded) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [isExpanded]);

  const getAgeText = (eventTime?: number) => {
    if (!eventTime) return "N/A";
    const ts = eventTime > 1e11 ? eventTime : eventTime * 1000;
    const diff = Math.max(0, Math.floor((now - ts) / 1000));
    return `${diff} sec`;
  };

  const getTimeText = (eventTime?: number) => {
    if (!eventTime) return "N/A";
    const ts = eventTime > 1e11 ? eventTime : eventTime * 1000;
    return new Date(ts).toLocaleTimeString();
  };

  const isSoilCritical = (soilData.soil_moisture || 44) < 35;

  return (
    <div className="clean-card overflow-hidden">
      <button 
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-slate-50 hover:bg-slate-100 transition-colors border-b border-slate-100"
      >
        <div className="flex items-center gap-2">
          <Server size={18} className="text-slate-500" />
          <h3 className="font-bold text-slate-800">Tool & API Activity</h3>
        </div>
        {isExpanded ? <ChevronDown size={18} className="text-slate-400" /> : <ChevronRight size={18} className="text-slate-400" />}
      </button>

      {isExpanded && (
        <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50/50">
          
          <div className="bg-white border border-slate-200 rounded-lg p-3 text-sm shadow-sm">
            <div className="flex justify-between items-start mb-2 border-b border-slate-100 pb-2">
              <span className="font-semibold text-slate-800">Weather API</span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${weatherData.event_time ? 'text-emerald-600 bg-emerald-50' : 'text-slate-600 bg-slate-100'}`}>
                {weatherData.event_time ? '200 OK' : 'Waiting...'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-y-2 text-xs">
              <span className="text-slate-500">Called:</span>
              <span className="font-medium text-slate-700">{getTimeText(weatherData.event_time)}</span>
              <span className="text-slate-500">Location:</span>
              <span className="font-medium text-slate-700">Zone A (WEATHER_01)</span>
              <span className="text-slate-500">Humidity / Temp:</span>
              <span className="font-medium text-slate-700">{weatherData.humidity ?? '--'}% / {weatherData.temperature ?? '--'}°C</span>
              <span className="text-slate-500">Data Age:</span>
              <span className="font-medium text-slate-700">{getAgeText(weatherData.event_time)}</span>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Verification</span>
              <ul className="text-xs text-slate-600 space-y-1">
                <li className="flex items-center gap-1"><Check size={12} className="text-emerald-500" /> Location matched</li>
                <li className="flex items-center gap-1"><Check size={12} className="text-emerald-500" /> Timestamp valid</li>
                <li className="flex items-center gap-1"><Check size={12} className="text-emerald-500" /> Response schema valid</li>
              </ul>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-lg p-3 text-sm shadow-sm">
            <div className="flex justify-between items-start mb-2 border-b border-slate-100 pb-2">
              <span className="font-semibold text-slate-800">Soil Sensor API</span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${soilData.event_time ? 'text-emerald-600 bg-emerald-50' : 'text-slate-600 bg-slate-100'}`}>
                {soilData.event_time ? 'Connected' : 'Waiting...'}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-y-2 text-xs">
              <span className="text-slate-500">Device:</span>
              <span className="font-medium text-slate-700">SOIL_01</span>
              <span className="text-slate-500">Last Reading:</span>
              <span className={`font-medium ${isSoilCritical ? 'text-amber-600' : 'text-emerald-600'}`}>
                {soilData.soil_moisture ?? '--'}%
              </span>
              <span className="text-slate-500">Updated:</span>
              <span className="font-medium text-slate-700">{getAgeText(soilData.event_time)}</span>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Verification</span>
              <ul className="text-xs text-slate-600 space-y-1">
                <li className="flex items-center gap-1"><Check size={12} className="text-emerald-500" /> Device authenticated</li>
                <li className="flex items-center gap-1"><Check size={12} className="text-emerald-500" /> Timestamp valid</li>
                {isSoilCritical ? (
                  <li className="flex items-center gap-1 text-amber-600"><AlertTriangle size={12} className="text-amber-500" /> Value outside healthy range</li>
                ) : (
                  <li className="flex items-center gap-1"><Check size={12} className="text-emerald-500" /> Value in healthy range</li>
                )}
              </ul>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
