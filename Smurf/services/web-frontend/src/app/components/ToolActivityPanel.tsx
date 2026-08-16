import React, { useState } from 'react';
import { Server, ChevronDown, ChevronRight, Check, AlertTriangle } from 'lucide-react';

export default function ToolActivityPanel() {
  const [isExpanded, setIsExpanded] = useState(false);

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
          
          <div className="bg-white border border-slate-200 rounded-lg p-3 text-sm">
            <div className="flex justify-between items-start mb-2 border-b border-slate-100 pb-2">
              <span className="font-semibold text-slate-800">Weather API</span>
              <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">200 OK</span>
            </div>
            <div className="grid grid-cols-2 gap-y-2 text-xs">
              <span className="text-slate-500">Called:</span>
              <span className="font-medium text-slate-700">08:31:02</span>
              <span className="text-slate-500">Location:</span>
              <span className="font-medium text-slate-700">Zone B</span>
              <span className="text-slate-500">Rain Prob:</span>
              <span className="font-medium text-slate-700">8%</span>
              <span className="text-slate-500">Data Age:</span>
              <span className="font-medium text-slate-700">32 sec</span>
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

          <div className="bg-white border border-slate-200 rounded-lg p-3 text-sm">
            <div className="flex justify-between items-start mb-2 border-b border-slate-100 pb-2">
              <span className="font-semibold text-slate-800">Soil Sensor API</span>
              <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">Connected</span>
            </div>
            <div className="grid grid-cols-2 gap-y-2 text-xs">
              <span className="text-slate-500">Device:</span>
              <span className="font-medium text-slate-700">S-021</span>
              <span className="text-slate-500">Last Reading:</span>
              <span className="font-medium text-slate-700">23%</span>
              <span className="text-slate-500">Updated:</span>
              <span className="font-medium text-slate-700">8 sec ago</span>
            </div>
            <div className="mt-3 pt-2 border-t border-slate-100">
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Verification</span>
              <ul className="text-xs text-slate-600 space-y-1">
                <li className="flex items-center gap-1"><Check size={12} className="text-emerald-500" /> Device authenticated</li>
                <li className="flex items-center gap-1"><Check size={12} className="text-emerald-500" /> Timestamp valid</li>
                <li className="flex items-center gap-1 text-amber-600"><AlertTriangle size={12} className="text-amber-500" /> Value outside healthy range</li>
              </ul>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
