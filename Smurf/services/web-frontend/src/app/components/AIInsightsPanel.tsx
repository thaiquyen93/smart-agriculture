import React from 'react';
import { AlertTriangle, CloudRain, Bot, ChevronRight } from 'lucide-react';
import { AIInsight } from '../lib/types';

interface AIInsightsPanelProps {
  insights: AIInsight[];
  onViewEvidence: (insight: AIInsight) => void;
}

export default function AIInsightsPanel({ insights, onViewEvidence }: AIInsightsPanelProps) {
  return (
    <div className="flex flex-col h-full gap-4">
      <h3 className="font-bold text-slate-800 flex items-center gap-2">
        AI Insights
      </h3>

      <div className="flex-1 space-y-3 overflow-y-auto pr-1">
        
        {/* Mocked Insights to match prompt examples perfectly */}
        
        <div className="clean-card border-l-4 border-l-red-500 p-4">
          <div className="flex items-center gap-2 text-red-600 mb-2">
            <AlertTriangle size={16} />
            <span className="text-xs font-bold uppercase tracking-wider">High Risk</span>
          </div>
          <h4 className="font-semibold text-slate-800 mb-1">Zone B</h4>
          <p className="text-sm text-slate-600 mb-3">
            Predicted soil moisture: <strong className="text-slate-800">19% in 4 hours</strong>
          </p>
          <div className="grid grid-cols-2 gap-2 mb-4 text-xs">
            <div className="bg-slate-50 p-2 rounded">
              <span className="text-slate-400 block mb-0.5">Confidence</span>
              <span className="font-semibold text-slate-700">91%</span>
            </div>
            <div className="bg-slate-50 p-2 rounded">
              <span className="text-slate-400 block mb-0.5">Impact</span>
              <span className="font-semibold text-slate-700">Crop water stress</span>
            </div>
          </div>
          <button 
            onClick={() => onViewEvidence(insights[0])}
            className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition-colors flex items-center justify-center gap-1"
          >
            View Evidence
          </button>
        </div>

        <div className="clean-card border-l-4 border-l-blue-400 p-4">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <CloudRain size={16} />
            <span className="text-xs font-bold uppercase tracking-wider">Weather Insight</span>
          </div>
          <p className="text-sm text-slate-600 mb-3">
            Rain probability: <strong className="text-slate-800">8%</strong>
          </p>
          <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
            <div className="bg-slate-50 p-2 rounded">
              <span className="text-slate-400 block mb-0.5">Next 6 hours</span>
              <span className="font-semibold text-slate-700">Low rainfall expected</span>
            </div>
            <div className="bg-slate-50 p-2 rounded">
              <span className="text-slate-400 block mb-0.5">Impact</span>
              <span className="font-semibold text-slate-700">Irrigation should proceed</span>
            </div>
          </div>
        </div>

        <div className="clean-card border-l-4 border-l-purple-500 p-4 bg-purple-50/30">
          <div className="flex items-center gap-2 text-purple-600 mb-2">
            <Bot size={16} />
            <span className="text-xs font-bold uppercase tracking-wider">AI Recommendation</span>
          </div>
          <h4 className="font-semibold text-slate-800 mb-1">Irrigate Zone B</h4>
          <p className="text-sm text-slate-600 mb-3">for 7 minutes</p>
          <div className="flex items-center justify-between mt-4">
            <span className="text-xs font-semibold text-red-600 bg-red-100 px-2 py-1 rounded">Priority: HIGH</span>
            <button className="text-xs font-semibold text-purple-700 flex items-center gap-1 hover:underline">
              Review Decision <ChevronRight size={14} />
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
