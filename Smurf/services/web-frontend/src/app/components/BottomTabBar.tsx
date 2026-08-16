"use client";

import React from "react";
import { TabId } from "../lib/types";
import { Home, LayoutDashboard, MessageCircle, User } from "lucide-react";

interface BottomTabBarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  unreadChat?: number;
}

const TABS: { id: TabId; label: string; Icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "home", label: "Home", Icon: Home },
  { id: "dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { id: "chat", label: "Chat AI", Icon: MessageCircle },
  { id: "profile", label: "Profile", Icon: User },
];

export default function BottomTabBar({ activeTab, onTabChange, unreadChat = 0 }: BottomTabBarProps) {
  return (
    <nav className="bottom-tab-bar" role="tablist">
      {TABS.map(({ id, label, Icon }) => (
        <button
          key={id}
          role="tab"
          aria-selected={activeTab === id}
          className={`tab-item ${activeTab === id ? "active" : ""}`}
          onClick={() => onTabChange(id)}
        >
          <div className="relative">
            <Icon className="w-5 h-5" />
            {id === "chat" && unreadChat > 0 && (
              <span className="absolute -top-1 -right-2 w-4 h-4 bg-rose-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                {unreadChat > 9 ? "9+" : unreadChat}
              </span>
            )}
          </div>
          <span className="text-[10px] mt-0.5">{label}</span>
        </button>
      ))}
    </nav>
  );
}
