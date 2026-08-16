"use client";

import React from "react";
import { AgentLogEntry } from "../lib/types";
import { AGENT_CONFIG } from "../lib/constants";
import { Network, ArrowDownCircle } from "lucide-react";

interface AgentActivityLogProps {
  logs: AgentLogEntry[];
}

export default function AgentActivityLog({ logs }: AgentActivityLogProps) {
  if (!logs || logs.length === 0) {
    return (
      <div className="glass-card p-8 text-center border-gray-800">
        <Network className="w-8 h-8 text-gray-600 mx-auto mb-3 opacity-50" />
        <p className="text-sm text-gray-500 font-mono">Chưa có luồng Agent nào được ghi nhận</p>
      </div>
    );
  }

  return (
    <div className="glass-card p-5 border-[#1A3A1C]">
      <div className="flex items-center gap-2 mb-6">
        <Network className="w-4 h-4 text-emerald-400" />
        <h3 className="text-sm font-bold text-white uppercase tracking-wider">Multi-Agent Activity Trace</h3>
      </div>

      <div className="relative pl-4 border-l border-[#1A3A1C] space-y-6">
        {logs.map((log, index) => {
          const config = AGENT_CONFIG[log.agent_name] || { icon: "🤖", color: "text-gray-400" };
          
          return (
            <div key={log.created_at + index} className="relative fade-in-up" style={{ animationDelay: `${index * 100}ms` }}>
              {/* Timeline Dot */}
              <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-[#0D1B0E] border-2 border-emerald-500/50" />
              
              {/* Agent Header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{config.icon}</span>
                  <span className={`text-xs font-bold font-mono ${config.color}`}>{log.agent_name}</span>
                </div>
                <span className="text-[10px] text-gray-500 font-mono">
                  {new Date(log.created_at).toLocaleTimeString('vi-VN')}
                </span>
              </div>

              {/* Action Type Badge */}
              <div className="inline-block px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider bg-gray-800/50 text-gray-400 border border-gray-700/50 mb-2">
                {log.action_type}
              </div>

              {/* Response Content */}
              <div className="bg-[#071108] p-3 rounded-lg border border-[#1A3A1C] text-sm text-gray-300 leading-relaxed mb-2">
                {log.output_response}
              </div>

              {/* Evidence Data Tags (Yêu cầu đề bài) */}
              {log.evidence_data && Object.keys(log.evidence_data).length > 0 && (
                <div className="flex items-start gap-2 mt-2">
                  <ArrowDownCircle className="w-3.5 h-3.5 text-gray-500 flex-shrink-0 mt-0.5" />
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(log.evidence_data).map(([key, value]) => (
                      <span key={key} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/5 text-emerald-400/60 border border-emerald-500/10">
                        {key}: {String(value)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
