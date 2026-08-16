"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChatMessage } from "../lib/types";
import { Send, X, Bot, Sparkles } from "lucide-react";

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

/** Pre-defined quick action buttons */
const QUICK_ACTIONS = [
  { label: "🌱 Kế hoạch tưới hôm nay", prompt: "Hãy chuẩn bị kế hoạch tưới cho khu A trong hôm nay và giải thích dữ liệu đã sử dụng." },
  { label: "🔍 Kiểm tra phiên tưới", prompt: "Hãy kiểm tra phiên tưới hiện tại và chuẩn bị công việc cần thực hiện nếu kết quả không như mong đợi." },
  { label: "⚠️ Báo cáo cảm biến", prompt: "Dữ liệu một số cảm biến vừa ngừng cập nhật. Hãy tiếp tục lập kế hoạch công việc cho đội ngoài hiện trường." },
];

/** Simulated multi-agent response flow for demo */
function generateAgentResponse(userMessage: string): ChatMessage[] {
  const sessionTs = Date.now();
  const responses: ChatMessage[] = [];

  // Step 1: Coordinator
  responses.push({
    id: `resp-${sessionTs}-1`,
    role: "assistant",
    content: "🧠 **Farm Coordinator Agent** đang phân tích yêu cầu...",
    timestamp: sessionTs,
    agent_name: "FarmCoordinatorAgent",
  });

  // Step 2: Field IoT
  responses.push({
    id: `resp-${sessionTs}-2`,
    role: "assistant",
    content: `📡 **Field IoT Agent** đã đọc dữ liệu:\n• SOIL_01: Độ ẩm 42.5%, Nhiệt độ 28.3°C\n• WEATHER_01: 31°C, Humidity 65%\n• TANK_01: Mực nước 82%\n• SUN_01: 52,000 Lux\n• PUMP_01: Flow 12.5 L/min, 750W`,
    timestamp: sessionTs + 1000,
    agent_name: "FieldIoTAgent",
    data_sources: ["SOIL_01", "WEATHER_01", "TANK_01", "SUN_01", "PUMP_01"],
  });

  if (userMessage.toLowerCase().includes("tưới") || userMessage.toLowerCase().includes("irrigat")) {
    // Step 3: Irrigation Agent
    responses.push({
      id: `resp-${sessionTs}-3`,
      role: "assistant",
      content: `💧 **Irrigation Planning Agent** đề xuất:\n\n**Kế hoạch tưới Khu A — Hôm nay**\n• ⏰ 06:00 — Tưới sáng sớm (ưu tiên CAO)\n• ⏰ 17:30 — Tưới chiều mát\n• 💧 Tổng: 450L nước\n\n📊 **Dữ liệu quyết định:**\n• Độ ẩm đất thấp (42.5% < 50%)\n• Nhiệt độ cao (31°C)\n• Ánh nắng mạnh (52k Lux)\n• Tank đủ nước (82%)`,
      timestamp: sessionTs + 2000,
      agent_name: "IrrigationPlanningAgent",
      data_sources: ["SOIL_01", "WEATHER_01", "TANK_01", "SUN_01"],
    });

    // Step 4: Resource Agent
    responses.push({
      id: `resp-${sessionTs}-4`,
      role: "assistant",
      content: `🪣 **Resource Agent** xác nhận:\n✅ Tank 82% — đủ nước cho 2 phiên tưới (450L)\n✅ PUMP_01 hoạt động bình thường\n✅ pH nước: 6.8 (tối ưu cho cây trồng)`,
      timestamp: sessionTs + 3000,
      agent_name: "ResourceAgent",
      data_sources: ["TANK_01", "PUMP_01", "PH_01"],
    });

    // Step 5: Action Agent
    responses.push({
      id: `resp-${sessionTs}-5`,
      role: "assistant",
      content: `⚡ **Farm Action Agent** đã thực hiện:\n\n✅ **Tool:** \`createIrrigationSchedule()\` → 200 OK\n✅ **Verification:** Đọc lại lịch → Lịch tưới đã tồn tại trong hệ thống\n\n📋 Kế hoạch chờ **phê duyệt** của bạn. Nhấn nút Phê duyệt ở tab Dashboard.`,
      timestamp: sessionTs + 4000,
      agent_name: "FarmActionAgent",
    });
  } else if (userMessage.toLowerCase().includes("kiểm tra") || userMessage.toLowerCase().includes("check")) {
    responses.push({
      id: `resp-${sessionTs}-3`,
      role: "assistant",
      content: `💧 **Irrigation Planning Agent** phân tích phiên tưới:\n• PUMP_01 đang hoạt động: 12.5 L/min\n• Độ ẩm đất hiện tại: 42.5% (cần tăng lên 60%)\n• Thời gian tưới dự kiến còn: ~15 phút`,
      timestamp: sessionTs + 2000,
      agent_name: "IrrigationPlanningAgent",
      data_sources: ["PUMP_01", "SOIL_01"],
    });

    responses.push({
      id: `resp-${sessionTs}-4`,
      role: "assistant",
      content: `⚡ **Farm Action Agent** đã tạo:\n\n📋 **Phiếu kiểm tra #TASK-${Date.now()}**\n• Kiểm tra lưu lượng PUMP_01 sau phiên tưới\n• Giao cho: Kỹ sư Nguyễn Văn A\n• Mức độ: ⚠️ WARNING\n\n✅ **Verification:** Phiếu kiểm tra đã tồn tại trong hệ thống`,
      timestamp: sessionTs + 3000,
      agent_name: "FarmActionAgent",
    });
  } else {
    responses.push({
      id: `resp-${sessionTs}-3`,
      role: "assistant",
      content: `🧠 **Farm Coordinator** tổng hợp:\n\nHệ thống nông trại đang hoạt động ổn định:\n• 6/6 thiết bị đang online\n• Không có cảnh báo nghiêm trọng\n• Kế hoạch tưới tiếp theo: 17:30 hôm nay\n\nBạn có thể hỏi tôi về:\n• Lập kế hoạch tưới\n• Kiểm tra phiên tưới\n• Tình trạng thiết bị\n• Báo cáo canh tác`,
      timestamp: sessionTs + 2000,
      agent_name: "FarmCoordinatorAgent",
    });
  }

  return responses;
}

export default function ChatPanel({ isOpen, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Xin chào! 🌾 Tôi là **Farm Coordinator AI**. Tôi có thể phối hợp các Agent để lập kế hoạch tưới, kiểm tra thiết bị, hoặc tạo nhiệm vụ. Bạn cần gì?",
      timestamp: Date.now(),
      agent_name: "FarmCoordinatorAgent",
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  const handleSend = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: messageText,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);

    // Simulate multi-agent processing delay
    const responses = generateAgentResponse(messageText);

    for (let i = 0; i < responses.length; i++) {
      await new Promise((resolve) => setTimeout(resolve, 800 + Math.random() * 400));
      setMessages((prev) => [...prev, responses[i]]);
    }

    setIsTyping(false);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] bg-[#071108] flex flex-col slide-in-right">
      {/* Chat Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1A3A1C]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-emerald-500/20 flex items-center justify-center">
            <Bot className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white">Farm AI Assistant</h2>
            <p className="text-[10px] text-emerald-500/70 font-mono">Multi-Agent Coordinator</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-full bg-gray-800/50 flex items-center justify-center hover:bg-gray-700/50 transition"
        >
          <X className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      {/* Quick Actions */}
      <div className="px-4 py-3 border-b border-[#1A3A1C] overflow-x-auto">
        <div className="flex gap-2">
          {QUICK_ACTIONS.map((action, i) => (
            <button
              key={i}
              onClick={() => handleSend(action.prompt)}
              className="flex-shrink-0 text-xs px-3 py-1.5 rounded-full border border-[#1A3A1C] bg-[#0D1B0E] text-emerald-400 hover:border-emerald-500/40 hover:bg-emerald-500/5 transition-all whitespace-nowrap"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} fade-in-up`}>
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-emerald-500/15 flex items-center justify-center flex-shrink-0 mr-2 mt-1">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
              </div>
            )}
            <div className={msg.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"}>
              {/* Agent name tag */}
              {msg.agent_name && (
                <span className="text-[10px] text-emerald-500/60 font-mono block mb-1">
                  {msg.agent_name}
                </span>
              )}
              {/* Render content with basic markdown-like formatting */}
              <div className="whitespace-pre-wrap leading-relaxed">
                {msg.content.split(/(\*\*.*?\*\*|`.*?`)/g).map((part, i) => {
                  if (part.startsWith("**") && part.endsWith("**")) {
                    return <strong key={i} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
                  }
                  if (part.startsWith("`") && part.endsWith("`")) {
                    return <code key={i} className="text-emerald-400 bg-emerald-500/10 px-1 rounded text-xs font-mono">{part.slice(1, -1)}</code>;
                  }
                  return <span key={i}>{part}</span>;
                })}
              </div>
              {/* Data source tags */}
              {msg.data_sources && msg.data_sources.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {msg.data_sources.map((src) => (
                    <span
                      key={src}
                      className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400/70 border border-emerald-500/20"
                    >
                      {src}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isTyping && (
          <div className="flex items-center gap-2 text-emerald-400/60 text-sm fade-in-up">
            <div className="w-7 h-7 rounded-full bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
            </div>
            <span className="text-xs font-mono">Agent đang xử lý...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-[#1A3A1C]" style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}>
        <div className="flex items-center gap-2 bg-[#0D1B0E] rounded-2xl border border-[#1A3A1C] px-4 py-2 focus-within:border-emerald-500/40 transition-colors">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Hỏi AI về nông trại..."
            className="flex-1 bg-transparent outline-none text-sm text-white placeholder-gray-600"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isTyping}
            className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center hover:bg-emerald-500/30 transition disabled:opacity-30"
          >
            <Send className="w-4 h-4 text-emerald-400" />
          </button>
        </div>
      </div>
    </div>
  );
}
