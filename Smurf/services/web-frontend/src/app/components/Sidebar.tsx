import React from 'react';
import { 
  Sprout, 
  LayoutDashboard, 
  Map, 
  Activity, 
  BrainCircuit, 
  ClipboardList, 
  Zap, 
  ListOrdered, 
  LineChart, 
  Bot, 
  Settings 
} from 'lucide-react';

interface SidebarProps {
  activePage?: string;
}

export default function Sidebar({ activePage = 'Overview' }: SidebarProps) {
  const navItems = [
    { name: 'Overview', icon: LayoutDashboard },
    { name: 'Farms', icon: Map },
    { name: 'Zones', icon: Activity },
    { name: 'Live Sensors', icon: Activity },
    { name: 'AI Insights', icon: BrainCircuit },
    { name: 'Plans & Tasks', icon: ClipboardList },
    { name: 'Automation', icon: Zap },
    { name: 'Execution Logs', icon: ListOrdered },
    { name: 'Data & Analytics', icon: LineChart },
    { name: 'Agents', icon: Bot },
    { name: 'Settings', icon: Settings },
  ];

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-64 bg-white border-r border-slate-200 flex flex-col z-40 hidden md:flex">
      <div className="p-6 flex items-center gap-3 border-b border-slate-100 h-[73px]">
        <div className="bg-emerald-100 p-2 rounded-lg text-emerald-600">
          <Sprout size={24} />
        </div>
        <h1 className="font-bold text-lg text-slate-800 leading-tight">
          Farm<br/><span className="text-emerald-600">Intelligence</span>
        </h1>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.name}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              activePage === item.name 
                ? 'bg-emerald-50 text-emerald-700' 
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            <item.icon size={18} className={activePage === item.name ? 'text-emerald-600' : 'text-slate-400'} />
            {item.name}
          </button>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-200 bg-slate-50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-slate-300 flex items-center justify-center text-slate-600 font-bold border-2 border-white shadow-sm">
            FM
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Farm Manager</p>
            <p className="text-xs text-emerald-600 flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Online
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
