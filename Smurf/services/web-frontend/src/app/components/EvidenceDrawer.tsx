import React from 'react';
import { X, Network, Brain, History, FileText } from 'lucide-react';
import { AIInsight } from '../lib/types';

interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  insight: AIInsight | null;
}

export default function EvidenceDrawer({ isOpen, onClose, insight }: EvidenceDrawerProps) {
  if (!isOpen) return null;

  return (
    <>
      <div 
        className="fixed inset-0 bg-slate-900/20 backdrop-blur-sm z-50 transition-opacity"
        onClick={onClose}
      />
      
      <div className="fixed right-0 top-0 bottom-0 w-full max-w-md bg-white shadow-2xl z-50 flex flex-col slide-in-right border-l border-slate-200">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-100 bg-slate-50">
          <h2 className="text-lg font-bold text-slate-800">Why did AI recommend irrigation?</h2>
          <button 
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-full transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          
          {/* Section 1: Input Data */}
          <section>
            <div className="flex items-center gap-2 mb-4">
              <Network size={18} className="text-slate-400" />
              <h3 className="font-semibold text-slate-700 text-sm tracking-widest uppercase">Input Data</h3>
            </div>
            
            <div className="grid grid-cols-2 gap-3">
              <div className="clean-card p-3 bg-slate-50">
                <span className="text-xs text-slate-500 block mb-1">Soil Moisture</span>
                <span className="text-lg font-bold text-slate-800">23%</span>
                <span className="text-[10px] text-slate-400 block mt-1">Updated 12 sec ago</span>
              </div>
              <div className="clean-card p-3 bg-slate-50">
                <span className="text-xs text-slate-500 block mb-1">Temperature</span>
                <span className="text-lg font-bold text-slate-800">34.1°C</span>
                <span className="text-[10px] text-slate-400 block mt-1">Updated 10 sec ago</span>
              </div>
              <div className="clean-card p-3 bg-slate-50">
                <span className="text-xs text-slate-500 block mb-1">Humidity</span>
                <span className="text-lg font-bold text-slate-800">61%</span>
              </div>
              <div className="clean-card p-3 bg-slate-50">
                <span className="text-xs text-slate-500 block mb-1">Rain Probability</span>
                <span className="text-lg font-bold text-slate-800">8%</span>
              </div>
            </div>

            <div className="mt-3 p-3 bg-slate-50 rounded-lg border border-slate-100 text-sm text-slate-600 flex items-start gap-2">
              <History size={16} className="text-slate-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-slate-700 block mb-0.5">Historical Pattern</span>
                Similar conditions caused 12% moisture decrease.
              </div>
            </div>
          </section>

          {/* Section 2: Model Output */}
          <section>
            <div className="flex items-center gap-2 mb-4">
              <Brain size={18} className="text-purple-500" />
              <h3 className="font-semibold text-slate-700 text-sm tracking-widest uppercase">Model Output</h3>
            </div>
            
            <div className="bg-purple-50/50 rounded-xl p-4 border border-purple-100">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <span className="text-xs text-slate-500 block mb-1">Predicted Moisture</span>
                  <span className="text-lg font-bold text-slate-800">19%</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block mb-1">Time Horizon</span>
                  <span className="text-lg font-bold text-slate-800">4 hours</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block mb-1">Confidence</span>
                  <span className="text-lg font-bold text-emerald-600">91%</span>
                </div>
              </div>
            </div>
          </section>

          {/* Section 3: Reasoning */}
          <section>
            <div className="flex items-center gap-2 mb-4">
              <FileText size={18} className="text-slate-400" />
              <h3 className="font-semibold text-slate-700 text-sm tracking-widest uppercase">Reasoning</h3>
            </div>
            
            <ol className="list-decimal list-inside space-y-2 text-sm text-slate-600 ml-1">
              <li>Soil moisture is below threshold.</li>
              <li>Moisture is decreasing rapidly.</li>
              <li>Temperature is high.</li>
              <li>Rain probability is low.</li>
              <li>Historical patterns indicate continued drying.</li>
            </ol>
          </section>

        </div>
        
        {/* Footer */}
        <div className="p-6 border-t border-slate-200">
          <button 
            onClick={onClose}
            className="w-full py-2.5 bg-slate-800 hover:bg-slate-900 text-white font-semibold rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </>
  );
}
