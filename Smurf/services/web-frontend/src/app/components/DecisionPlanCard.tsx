import React from 'react';
import { Bot, User, Clock, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { Plan } from '../lib/types';

interface DecisionPlanCardProps {
  plan: Plan;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export default function DecisionPlanCard({ plan, onApprove, onReject }: DecisionPlanCardProps) {
  
  // Status mapping
  const isPending = plan.status === 'pending_approval';
  
  return (
    <div className={`clean-card p-0 overflow-hidden ${isPending ? 'border-amber-200 shadow-sm' : ''}`}>
      {/* Header */}
      <div className={`px-5 py-4 flex items-center justify-between border-b ${isPending ? 'bg-amber-50/50 border-amber-100' : 'bg-slate-50 border-slate-100'}`}>
        <div>
          <h3 className="font-bold text-slate-800 tracking-tight uppercase">{plan.action.split(' ')[0]} PLAN</h3>
          <p className="text-sm text-slate-600 font-medium">{plan.zoneId} • {plan.action}</p>
        </div>
        {isPending && (
          <span className="status-badge status-badge-warning animate-pulse">
            <Clock size={12}/> Waiting for Approval
          </span>
        )}
        {!isPending && (
          <span className="status-badge status-badge-healthy">
            <CheckCircle size={12}/> Approved
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-5">
        <div className="flex flex-col md:flex-row gap-6">
          
          {/* Details */}
          <div className="flex-1 space-y-4">
            {isPending && (
              <div className="flex items-start gap-3 p-3 bg-red-50 text-red-700 rounded-lg border border-red-100">
                <AlertTriangle size={18} className="shrink-0 mt-0.5" />
                <div className="text-sm">
                  <p className="font-bold mb-1">ACTION REQUIRES APPROVAL</p>
                  <p>Duration: <span className="font-semibold">{plan.duration}</span></p>
                  <p>Expected Water Usage: <span className="font-semibold">{plan.expectedUsage}</span></p>
                  <p className="mt-2 text-red-600">Reason: {plan.reason}</p>
                </div>
              </div>
            )}
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-slate-400 block mb-1">Priority</span>
                <span className="font-semibold text-red-600 bg-red-100 px-2 py-0.5 rounded">HIGH</span>
              </div>
              <div className="col-span-2">
                <span className="text-slate-400 block mb-1">Based on</span>
                <div className="flex flex-wrap gap-2 text-xs font-medium text-slate-600">
                  <span className="bg-slate-100 px-2 py-1 rounded">✓ Soil Sensor</span>
                  <span className="bg-slate-100 px-2 py-1 rounded">✓ Weather API</span>
                  <span className="bg-slate-100 px-2 py-1 rounded">✓ Historical Data</span>
                  <span className="bg-slate-100 px-2 py-1 rounded">✓ AI Prediction</span>
                </div>
              </div>
            </div>
          </div>

          {/* Workflow & Responsibilities */}
          <div className="md:w-64 shrink-0 flex flex-col justify-between">
            <div className="space-y-3 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded bg-purple-100 text-purple-600 flex items-center justify-center shrink-0">
                  <Bot size={14} />
                </div>
                <div className="flex flex-col">
                  <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider leading-none">Created by</span>
                  <span className="font-semibold text-slate-700">{plan.responsibleAgent}</span>
                </div>
              </div>
              
              {!isPending && (
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0">
                    <User size={14} />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider leading-none">Approved by</span>
                    <span className="font-semibold text-slate-700">Farm Manager</span>
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            {isPending && (
              <div className="mt-4 flex flex-col gap-2">
                <button 
                  onClick={() => onApprove(plan.id)}
                  className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2 text-sm shadow-sm"
                >
                  <CheckCircle size={16} /> APPROVE ACTION
                </button>
                <div className="flex gap-2">
                  <button 
                    onClick={() => onReject(plan.id)}
                    className="flex-1 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 font-medium rounded-lg transition-colors text-xs flex items-center justify-center gap-1"
                  >
                    <XCircle size={14} /> REJECT
                  </button>
                  <button className="flex-1 py-1.5 bg-white border border-slate-200 hover:bg-slate-50 text-slate-600 font-medium rounded-lg transition-colors text-xs">
                    MODIFY PLAN
                  </button>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
