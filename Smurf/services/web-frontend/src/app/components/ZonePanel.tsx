import React from 'react';
import { Droplet, Thermometer, AlertCircle, CheckCircle2 } from 'lucide-react';
import { SensorReading } from '../lib/types';

interface ZonePanelProps {
  zones: {
    id: string;
    name: string;
    status: 'healthy' | 'warning' | 'critical' | 'irrigating';
    soilMoisture: number;
    temperature: number;
    lastUpdate: string;
  }[];
  onZoneClick: (zoneId: string) => void;
}

export default function ZonePanel({ zones, onZoneClick }: ZonePanelProps) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-slate-800 flex items-center gap-2">
          Zones
          <span className="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded-full font-medium">
            {zones.length}
          </span>
        </h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-3">
        {zones.map((zone) => (
          <div 
            key={zone.id}
            onClick={() => onZoneClick(zone.id)}
            className="clean-card p-4 cursor-pointer hover:border-emerald-200 transition-colors group"
          >
            <div className="flex justify-between items-start mb-3">
              <span className="font-semibold text-slate-800 group-hover:text-emerald-700 transition-colors">
                {zone.name}
              </span>
              {zone.status === 'healthy' && (
                <span className="status-badge status-badge-healthy"><CheckCircle2 size={12}/> Healthy</span>
              )}
              {zone.status === 'warning' && (
                <span className="status-badge status-badge-warning"><AlertCircle size={12}/> Warning</span>
              )}
              {zone.status === 'critical' && (
                <span className="status-badge status-badge-critical"><AlertCircle size={12}/> Critical</span>
              )}
              {zone.status === 'irrigating' && (
                <span className="status-badge status-badge-ai"><Droplet size={12}/> Irrigating</span>
              )}
            </div>

            <div className="flex items-center gap-6 mt-2">
              <div className="flex items-center gap-2">
                <Droplet size={18} className="text-blue-500" />
                <div className="flex flex-col">
                  <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Moisture</span>
                  <span className="font-semibold text-slate-700">{zone.soilMoisture}%</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Thermometer size={18} className="text-amber-500" />
                <div className="flex flex-col">
                  <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">Temp</span>
                  <span className="font-semibold text-slate-700">{zone.temperature}°C</span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
              <span className="text-[10px] text-slate-400">Updated {zone.lastUpdate}</span>
              <button className="text-[11px] font-medium text-emerald-600 hover:text-emerald-700">
                View Details &rarr;
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
