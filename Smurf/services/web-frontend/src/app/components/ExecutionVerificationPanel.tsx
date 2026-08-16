import React from 'react';
import { Terminal, Database, Activity, Target, CheckCircle2, XCircle } from 'lucide-react';
import { Verification } from '../lib/types';

interface ExecutionVerificationPanelProps {
  verifications: {
    command: string;
    deviceStatus: string;
    flowStatus: string;
    duration: string;
    sensorResult: Verification;
    finalStatus: 'verified' | 'failed';
  }[];
}

export default function ExecutionVerificationPanel({ verifications }: ExecutionVerificationPanelProps) {
  return (
    <div className="flex flex-col gap-4">
      <h3 className="font-bold text-slate-800 flex items-center gap-2">
        Execution & Verification
      </h3>

      <div className="grid grid-cols-1 gap-4">
        {verifications.map((ver, idx) => (
          <div key={idx} className={`clean-card ${ver.finalStatus === 'failed' ? 'border-red-200' : ''}`}>
            {/* Visual Pipeline */}
            <div className="flex flex-wrap items-center justify-between p-4 border-b border-slate-100 bg-slate-50 overflow-x-auto text-xs font-semibold text-slate-500 uppercase tracking-wider">
              <div className="flex items-center gap-2 min-w-max">
                <Terminal size={14} className="text-slate-400" />
                COMMAND
                <span className="mx-2 text-slate-300">→</span>
              </div>
              <div className="flex items-center gap-2 min-w-max">
                <Database size={14} className="text-slate-400" />
                PUMP
                <span className="mx-2 text-slate-300">→</span>
              </div>
              <div className="flex items-center gap-2 min-w-max">
                <Activity size={14} className="text-slate-400" />
                FLOW SENSOR
                <span className="mx-2 text-slate-300">→</span>
              </div>
              <div className="flex items-center gap-2 min-w-max">
                <Target size={14} className="text-slate-400" />
                SOIL SENSOR
                <span className="mx-2 text-slate-300">→</span>
              </div>
              <div className="flex items-center gap-2 min-w-max">
                <CheckCircle2 size={14} className={ver.finalStatus === 'verified' ? 'text-emerald-500' : 'text-slate-400'} />
                VERIFICATION
              </div>
            </div>

            {/* Results */}
            <div className="p-4 grid grid-cols-2 md:grid-cols-5 gap-4">
              <div>
                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Command</span>
                <p className="font-semibold text-slate-800">{ver.command}</p>
                <p className="text-[10px] font-medium text-emerald-600 mt-0.5">✓ Sent</p>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Device</span>
                <p className="font-semibold text-slate-800">{ver.deviceStatus}</p>
                <p className="text-[10px] font-medium text-emerald-600 mt-0.5">✓ Confirmed</p>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Flow / Duration</span>
                <p className="font-semibold text-slate-800">{ver.flowStatus}</p>
                <p className="text-[10px] font-medium text-emerald-600 mt-0.5">✓ {ver.duration}</p>
              </div>
              
              <div className="col-span-2 md:border-l md:border-slate-100 md:pl-4">
                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block mb-1">Final Outcome</span>
                <div className="flex items-start gap-4">
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-slate-800">
                      {ver.sensorResult.expected} → {ver.sensorResult.actual}
                    </p>
                    <p className={`text-[10px] font-medium mt-0.5 ${ver.sensorResult.status === 'passed' ? 'text-emerald-600' : 'text-red-600'}`}>
                      {ver.sensorResult.status === 'passed' ? '✓ Improved' : '❌ Failed to reach target'}
                    </p>
                  </div>
                  {ver.finalStatus === 'verified' ? (
                    <div className="bg-emerald-100 text-emerald-700 px-3 py-1.5 rounded-md text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 border border-emerald-200">
                      <CheckCircle2 size={14} /> Verified
                    </div>
                  ) : (
                    <div className="bg-red-100 text-red-700 px-3 py-1.5 rounded-md text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 border border-red-200">
                      <XCircle size={14} /> Failed
                    </div>
                  )}
                </div>
                
                {ver.finalStatus === 'failed' && (
                  <div className="mt-3 bg-red-50 p-2 rounded border border-red-100 text-xs">
                    <p className="font-semibold text-red-800 mb-1">Possible cause: Pump pressure abnormal</p>
                    <div className="flex gap-2 mt-2">
                      <button className="px-2 py-1 bg-white border border-red-200 text-red-700 rounded hover:bg-red-50 font-medium">Create Alert</button>
                      <button className="px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 font-medium">Manual Override</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
