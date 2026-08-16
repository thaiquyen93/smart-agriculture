import React from 'react';
import { CheckCircle2, Circle, Clock, AlertCircle } from 'lucide-react';
import { TaskItem } from '../lib/types';

interface TaskTableProps {
  tasks: TaskItem[];
}

export default function TaskTable({ tasks }: TaskTableProps) {
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'Completed': return <CheckCircle2 size={16} className="text-emerald-500" />;
      case 'In Progress': return <Clock size={16} className="text-blue-500" />;
      case 'Waiting Approval': return <AlertCircle size={16} className="text-amber-500" />;
      default: return <Circle size={16} className="text-slate-300" />;
    }
  };

  return (
    <div className="clean-card overflow-hidden">
      <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-white">
        <h3 className="font-bold text-slate-800">Task Management</h3>
        <div className="flex gap-2">
          <select className="text-xs bg-slate-50 border border-slate-200 rounded px-2 py-1 outline-none text-slate-600">
            <option>All Tasks</option>
            <option>My Tasks</option>
            <option>AI Tasks</option>
          </select>
        </div>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-slate-500 uppercase bg-slate-50 border-b border-slate-100">
            <tr>
              <th className="px-4 py-3 font-semibold tracking-wider">Task</th>
              <th className="px-4 py-3 font-semibold tracking-wider">Zone</th>
              <th className="px-4 py-3 font-semibold tracking-wider">Responsible</th>
              <th className="px-4 py-3 font-semibold tracking-wider">Priority</th>
              <th className="px-4 py-3 font-semibold tracking-wider">Status</th>
              <th className="px-4 py-3 font-semibold tracking-wider">Due</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {tasks.map((task) => (
              <tr key={task.id} className="hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-3 font-medium text-slate-800">{task.title}</td>
                <td className="px-4 py-3 text-slate-600">{task.zone}</td>
                <td className="px-4 py-3 text-slate-600 flex items-center gap-1.5">
                  {task.responsible.includes('Agent') ? '🤖' : '👤'} {task.responsible}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase ${
                    task.priority === 'HIGH' ? 'bg-red-100 text-red-700' :
                    task.priority === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                    'bg-slate-100 text-slate-700'
                  }`}>
                    {task.priority}
                  </span>
                </td>
                <td className="px-4 py-3 flex items-center gap-1.5 font-medium text-slate-700">
                  {getStatusIcon(task.status)}
                  {task.status}
                </td>
                <td className="px-4 py-3 text-slate-500 font-mono text-xs">{task.dueTime}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
