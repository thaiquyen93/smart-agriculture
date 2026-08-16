"use client";

import React from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine 
} from 'recharts';

interface SensorTrendPanelProps {
  data: any[];
  selectedMetric?: string;
}

export default function SensorTrendPanel({ data, selectedMetric = "Soil Moisture" }: SensorTrendPanelProps) {
  
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white border border-slate-200 p-3 rounded-lg shadow-lg">
          <p className="font-semibold text-slate-700 mb-1">{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }}></span>
              <span className="text-slate-600">{entry.name}:</span>
              <span className="font-bold text-slate-800">
                {entry.value}{selectedMetric === "Soil Moisture" ? "%" : ""}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="clean-card flex flex-col h-full">
      <div className="p-5 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h3 className="font-bold text-slate-800">Sensor Trends</h3>
          <p className="text-xs text-slate-500 mt-1">Historical vs AI Predicted Data</p>
        </div>
        
        <div className="flex bg-slate-100 p-1 rounded-lg">
          <button className="px-3 py-1 text-xs font-semibold rounded-md bg-white text-slate-800 shadow-sm">6h</button>
          <button className="px-3 py-1 text-xs font-medium text-slate-500 hover:text-slate-700">24h</button>
          <button className="px-3 py-1 text-xs font-medium text-slate-500 hover:text-slate-700">7d</button>
        </div>
      </div>

      <div className="p-5 flex-1 min-h-[300px]">
        <div className="flex items-center gap-6 mb-6">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
            <span className="text-sm font-medium text-slate-600">Actual {selectedMetric}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-purple-500 border-2 border-white shadow-sm"></div>
            <span className="text-sm font-medium text-slate-600">AI Prediction</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-0 border-t-2 border-dashed border-red-400"></div>
            <span className="text-sm font-medium text-slate-600">Critical Threshold</span>
          </div>
        </div>

        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 5, right: 20, left: -20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
              <XAxis 
                dataKey="time" 
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#94A3B8', fontSize: 12 }}
                dy={10}
              />
              <YAxis 
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#94A3B8', fontSize: 12 }}
                domain={[10, 60]}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={25} stroke="#EF4444" strokeDasharray="4 4" />
              
              <Line 
                type="monotone" 
                dataKey="actual" 
                name="Actual"
                stroke="#10B981" 
                strokeWidth={3}
                dot={{ r: 4, strokeWidth: 2, fill: '#fff' }}
                activeDot={{ r: 6, strokeWidth: 0 }}
                connectNulls
              />
              <Line 
                type="monotone" 
                dataKey="prediction" 
                name="Prediction"
                stroke="#8B5CF6" 
                strokeWidth={3}
                strokeDasharray="5 5"
                dot={false}
                activeDot={{ r: 6, strokeWidth: 0 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
