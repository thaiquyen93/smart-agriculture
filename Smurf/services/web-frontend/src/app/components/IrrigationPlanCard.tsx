"use client";

import React, { useState } from "react";
import { IrrigationPlan } from "../lib/types";
import { CheckCircle2, Clock, Droplets, MapPin, AlertCircle, XCircle } from "lucide-react";

interface IrrigationPlanCardProps {
  plan: IrrigationPlan;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export default function IrrigationPlanCard({ plan, onApprove, onReject }: IrrigationPlanCardProps) {
  const [isVerifying, setIsVerifying] = useState(false);

  const handleApprove = () => {
    setIsVerifying(true);
    // Simulate verification delay
    setTimeout(() => {
      onApprove(plan.plan_id);
      setIsVerifying(false);
    }, 1500);
  };

  return (
    <div className="glass-card p-4 fade-in-up border-emerald-500/20">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">Kế hoạch tưới</h3>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-gray-400">
            <MapPin className="w-3.5 h-3.5" />
            <span>{plan.area_id}</span>
          </div>
        </div>

        {/* Status Badge */}
        <div className={`status-badge ${
          plan.status === 'PENDING_APPROVAL' ? 'text-amber-400 bg-amber-500/10 border-amber-500/30' :
          plan.status === 'APPROVED' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' :
          plan.status === 'REJECTED' ? 'text-rose-400 bg-rose-500/10 border-rose-500/30' :
          'text-sky-400 bg-sky-500/10 border-sky-500/30'
        }`}>
          {plan.status === 'PENDING_APPROVAL' ? 'Chờ duyệt' :
           plan.status === 'APPROVED' ? 'Đã duyệt' :
           plan.status === 'REJECTED' ? 'Đã từ chối' : plan.status}
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-[#071108] rounded-xl p-3 border border-[#1A3A1C]">
          <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-1">
            <Clock className="w-3.5 h-3.5 text-sky-400" />
            <span>Thời gian</span>
          </div>
          <div className="text-sm font-bold text-white">{plan.suggested_time}</div>
        </div>
        <div className="bg-[#071108] rounded-xl p-3 border border-[#1A3A1C]">
          <div className="flex items-center gap-1.5 text-xs text-gray-400 mb-1">
            <Droplets className="w-3.5 h-3.5 text-cyan-400" />
            <span>Lượng nước</span>
          </div>
          <div className="text-sm font-bold text-white">{plan.water_amount_liters} Lít</div>
        </div>
      </div>

      {/* Data Evidence (Yêu cầu đề bài) */}
      <div className="mb-4">
        <h4 className="text-xs font-semibold text-gray-400 mb-2 flex items-center gap-1.5">
          <AlertCircle className="w-3.5 h-3.5" />
          Dữ liệu quyết định
        </h4>
        <p className="text-sm text-gray-300 leading-relaxed bg-[#071108] p-3 rounded-xl border border-[#1A3A1C]">
          {plan.reasoning_summary}
        </p>

        {plan.data_evidence && plan.data_evidence.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {plan.data_evidence.map((ev, i) => (
              <span key={i} className="text-[10px] font-mono px-2 py-1 rounded bg-emerald-500/10 text-emerald-400/80 border border-emerald-500/20">
                {ev.device_id}: {ev.value}{ev.unit}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Actions / Verification */}
      {plan.status === 'PENDING_APPROVAL' && (
        <div className="flex gap-3 mt-5">
          <button 
            onClick={() => onReject(plan.plan_id)}
            disabled={isVerifying}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition-colors disabled:opacity-50"
          >
            Từ chối
          </button>
          <button 
            onClick={handleApprove}
            disabled={isVerifying}
            className="flex-1 py-2.5 rounded-xl text-sm font-bold bg-emerald-500 text-white hover:bg-emerald-600 shadow-[0_0_15px_rgba(16,185,129,0.3)] transition-all flex items-center justify-center gap-2 disabled:opacity-70"
          >
            {isVerifying ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Đang xác minh...
              </>
            ) : (
              'Phê duyệt'
            )}
          </button>
        </div>
      )}

      {/* Verification Result */}
      {plan.verification_result && plan.status === 'APPROVED' && (
        <div className="mt-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex gap-3 items-start">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
          <div>
            <h5 className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-0.5">Xác minh thành công</h5>
            <p className="text-[11px] text-gray-400 font-mono">{plan.verification_result.message}</p>
          </div>
        </div>
      )}

      {/* Agent Tag */}
      <div className="mt-4 pt-3 border-t border-[#1A3A1C] flex justify-between items-center">
        <span className="text-[10px] text-gray-500 font-mono">ID: {plan.plan_id}</span>
        <div className="flex items-center gap-1.5 text-[10px] font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
          <span>🧠</span>
          IrrigationAgent
        </div>
      </div>
    </div>
  );
}
