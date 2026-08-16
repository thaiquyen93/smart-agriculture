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
        
        {insights.length === 0 ? (
          <div className="clean-card p-6 text-center text-slate-500 font-medium font-mono text-xs border border-dashed border-slate-200">
            No active AI insights at this moment.
          </div>
        ) : (
          insights.map((insight, idx) => {
            let borderColor = "border-l-blue-400";
            let iconColor = "text-blue-600";
            let Icon = Bot;
            let label = "AI Insight";
            let bgClass = "";

            if (insight.priority === 'critical' || insight.priority === 'high') {
              borderColor = "border-l-red-500";
              iconColor = "text-red-600";
              Icon = AlertTriangle;
              label = "High Risk";
            } else if (insight.prediction.toLowerCase().includes('rain') || insight.prediction.toLowerCase().includes('weather')) {
              borderColor = "border-l-blue-400";
              iconColor = "text-blue-600";
              Icon = CloudRain;
              label = "Weather Insight";
            } else {
              borderColor = "border-l-purple-500";
              iconColor = "text-purple-600";
              bgClass = "bg-purple-50/30";
              label = "AI Recommendation";
            }

            return (
              <div key={idx} className={`clean-card border-l-4 ${borderColor} p-4 ${bgClass}`}>
                <div className={`flex items-center gap-2 ${iconColor} mb-2`}>
                  <Icon size={16} />
                  <span className="text-xs font-bold uppercase tracking-wider">{label}</span>
                </div>
                <h4 className="font-semibold text-slate-800 mb-1">{insight.zoneId}</h4>
                <p className="text-sm text-slate-600 mb-3">
                  {insight.prediction}
                </p>
                <div className="grid grid-cols-2 gap-2 mb-4 text-xs">
                  <div className="bg-slate-50 p-2 rounded">
                    <span className="text-slate-400 block mb-0.5">Confidence</span>
                    <span className="font-semibold text-slate-700">{insight.confidence}%</span>
                  </div>
                  <div className="bg-slate-50 p-2 rounded">
                    <span className="text-slate-400 block mb-0.5">Action</span>
                    <span className="font-semibold text-slate-700">{insight.recommendation}</span>
                  </div>
                </div>
                {insight.evidenceId && (
                  <button 
                    onClick={() => onViewEvidence(insight)}
                    className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition-colors flex items-center justify-center gap-1"
                  >
                    View Evidence
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
