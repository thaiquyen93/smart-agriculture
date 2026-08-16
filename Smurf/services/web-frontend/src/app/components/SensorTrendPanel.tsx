"use client";

import React from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine 
} from 'recharts';

export interface TrendLineDef {
  key: string;
  name: string;
  color: string;
  isPrediction?: boolean;
}

interface SensorTrendPanelProps {
  data: any[];
  lines: TrendLineDef[];
  title?: string;
}

export default function SensorTrendPanel({ data, lines, title = "Sensor Trends" }: SensorTrendPanelProps) {
  
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white border border-slate-200 p-3 rounded-lg shadow-lg z-50">
          <p className="font-semibold text-slate-700 mb-1">{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }}></span>
              <span className="text-slate-600">{entry.name}:</span>
              <span className="font-bold text-slate-800">
                {typeof entry.value === 'number' ? entry.value.toFixed(1) : entry.value}
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
          <h3 className="font-bold text-slate-800">{title}</h3>
          <p className="text-xs text-slate-500 mt-1">Historical vs AI Predicted Data</p>
        </div>
        
        <div className="flex bg-slate-100 p-1 rounded-lg">
          <button className="px-3 py-1 text-xs font-semibold rounded-md bg-white text-slate-800 shadow-sm">6h</button>
          <button className="px-3 py-1 text-xs font-medium text-slate-500 hover:text-slate-700">24h</button>
          <button className="px-3 py-1 text-xs font-medium text-slate-500 hover:text-slate-700">7d</button>
        </div>
      </div>

      <div className="p-5 flex-1 flex flex-col items-center justify-center min-h-[300px]">
        <div className="flex flex-wrap items-center justify-center gap-6 mb-6">
          {lines.map((line) => (
            <div key={line.key} className="flex items-center gap-2">
              <div 
                className={`w-3 h-3 rounded-full ${line.isPrediction ? "border-2 border-white shadow-sm" : ""}`}
                style={{ backgroundColor: line.color }}
              ></div>
              <span className="text-sm font-medium text-slate-600">{line.name}</span>
            </div>
          ))}
          <div className="flex items-center gap-2">
            <div className="w-8 h-0 border-t-2 border-dashed border-red-400"></div>
            <span className="text-sm font-medium text-slate-600">Critical Threshold</span>
          </div>
        </div>

        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 10, right: 20, left: -20, bottom: 10 }}
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
                domain={['dataMin - 5', 'dataMax + 5']}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={25} stroke="#EF4444" strokeDasharray="4 4" />
              
              {lines.map((line) => (
                <Line 
                  key={line.key}
                  type="monotone" 
                  dataKey={line.key} 
                  name={line.name}
                  stroke={line.color} 
                  strokeWidth={3}
                  strokeDasharray={line.isPrediction ? "5 5" : undefined}
                  dot={line.isPrediction ? false : { r: 4, strokeWidth: 2, fill: '#fff' }}
                  activeDot={{ r: 6, strokeWidth: 0 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
