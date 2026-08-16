import React from 'react';
import { Droplet, Thermometer, AlertCircle, CheckCircle2, Zap, Activity, FlaskConical, Database, Sun } from 'lucide-react';

interface DevicePanelProps {
  devices: {
    id: string;
    name: string;
    status: 'healthy' | 'warning' | 'critical' | 'irrigating';
    lastUpdate: string;
    metrics: {
      key: string;
      label: string;
      value: number | string;
      unit: string;
    }[];
  }[];
  selectedDeviceId?: string;
  onDeviceClick: (deviceId: string) => void;
  onViewDetails?: (deviceId: string) => void;
}

const getMetricIcon = (key: string) => {
  switch (key) {
    case 'moisture': return <Droplet size={16} className="text-blue-500" />;
    case 'temp': return <Thermometer size={16} className="text-amber-500" />;
    case 'humidity': return <Droplet size={16} className="text-sky-500" />;
    case 'flow_rate': return <Activity size={16} className="text-cyan-500" />;
    case 'power': return <Zap size={16} className="text-yellow-500" />;
    case 'ph': return <FlaskConical size={16} className="text-fuchsia-500" />;
    case 'level': return <Database size={16} className="text-indigo-500" />;
    case 'lux': return <Sun size={16} className="text-yellow-400" />;
    default: return <Activity size={16} className="text-slate-500" />;
  }
};

export default function DevicePanel({ devices, selectedDeviceId, onDeviceClick, onViewDetails }: DevicePanelProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-slate-800 flex items-center gap-2">
          Devices
          <span className="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded-full font-medium">
            {devices.length}
          </span>
        </h3>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-2">
        {devices.map((device) => {
          const isSelected = selectedDeviceId === device.id;
          return (
          <div 
            key={device.id}
            onClick={() => onDeviceClick(device.id)}
            className={`clean-card p-3 cursor-pointer transition-colors group ${isSelected ? 'border-emerald-500 ring-1 ring-emerald-500 shadow-md' : 'hover:border-emerald-200'}`}
          >
            <div className="flex justify-between items-start mb-1.5">
              <span className="font-semibold text-sm text-slate-800 group-hover:text-emerald-700 transition-colors">
                {device.name}
              </span>
              {device.status === 'healthy' && (
                <span className="status-badge status-badge-healthy"><CheckCircle2 size={12}/> Healthy</span>
              )}
              {device.status === 'warning' && (
                <span className="status-badge status-badge-warning"><AlertCircle size={12}/> Warning</span>
              )}
              {device.status === 'critical' && (
                <span className="status-badge status-badge-critical"><AlertCircle size={12}/> Critical</span>
              )}
              {device.status === 'irrigating' && (
                <span className="status-badge status-badge-ai"><Droplet size={12}/> Irrigating</span>
              )}
            </div>

            <div className="flex items-center gap-6 mt-1 flex-wrap">
              {device.metrics.map((m, i) => (
                <div key={i} className="flex items-center gap-2">
                  {getMetricIcon(m.key)}
                  <div className="flex flex-col">
                    <span className="text-[9px] text-slate-400 font-medium uppercase tracking-wider">{m.label}</span>
                    <span className="font-semibold text-sm text-slate-700">{m.value}{m.unit}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between">
              <span className="text-[9px] text-slate-400">Updated {device.lastUpdate}</span>
              {onViewDetails ? (
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewDetails(device.id);
                  }}
                  className="text-[10px] font-medium text-emerald-600 hover:text-emerald-700"
                >
                  View Details &rarr;
                </button>
              ) : (
                <div />
              )}
            </div>
          </div>
        )})}
      </div>
    </div>
  );
}
