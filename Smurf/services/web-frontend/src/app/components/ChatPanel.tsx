"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChatMessage } from "../lib/types";
import { Send, X, Bot, Sparkles, Loader2 } from "lucide-react";

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

/** Agent name → emoji/icon mapping */
const AGENT_ICONS: Record<string, string> = {
  Router: "🧭",
  FieldIoT: "📡",
  Agronomy: "🌿",
  Resource: "🪣",
  Coordinator: "🧠",
  Action: "⚡",
  Verifier: "✅",
  Narrative: "📝",
  PolicyGate: "🛡️",
  FarmCoordinatorAgent: "🧠",
};

/** Phase → human-readable Vietnamese label */
const PHASE_LABELS: Record<string, string> = {
  ROUTING: "Phân loại yêu cầu",
  DISPATCHING: "Giao việc cho Agent",
  ACTING: "Lập kế hoạch hành động",
  VERIFYING: "Xác minh kết quả",
  NARRATIVE: "Viết báo cáo tổng hợp",
};

/** Fallback mock responses when agent-core is offline */
function generateFallbackResponse(userMessage: string): ChatMessage[] {
  const ts = Date.now();
  const responses: ChatMessage[] = [];

  responses.push({
    id: `resp-${ts}-1`,
    role: "assistant",
    content: "🧠 **Farm Coordinator Agent** đang phân tích yêu cầu...",
    timestamp: ts,
    agent_name: "FarmCoordinatorAgent",
  });

  responses.push({
    id: `resp-${ts}-2`,
    role: "assistant",
    content: `📡 **Field IoT Agent** đã đọc dữ liệu:\n• SOIL_01: Độ ẩm 42.5%, Nhiệt độ 28.3°C\n• WEATHER_01: 31°C, Humidity 65%\n• TANK_01: Mực nước 82%\n• SUN_01: 52,000 Lux\n• PUMP_01: Flow 12.5 L/min, 750W`,
    timestamp: ts + 1000,
    agent_name: "FieldIoTAgent",
    data_sources: ["SOIL_01", "WEATHER_01", "TANK_01", "SUN_01", "PUMP_01"],
  });

  if (userMessage.toLowerCase().includes("tưới") || userMessage.toLowerCase().includes("irrigat")) {
    responses.push({
      id: `resp-${ts}-3`,
      role: "assistant",
      content: `💧 **Irrigation Planning Agent** đề xuất:\n\n**Kế hoạch tưới Khu A — Hôm nay**\n• ⏰ 06:00 — Tưới sáng sớm (ưu tiên CAO)\n• ⏰ 17:30 — Tưới chiều mát\n• 💧 Tổng: 450L nước\n\n📊 **Dữ liệu quyết định:**\n• Độ ẩm đất thấp (42.5% < 50%)\n• Nhiệt độ cao (31°C)\n• Ánh nắng mạnh (52k Lux)\n• Tank đủ nước (82%)`,
      timestamp: ts + 2000,
      agent_name: "IrrigationPlanningAgent",
      data_sources: ["SOIL_01", "WEATHER_01", "TANK_01", "SUN_01"],
    });

    responses.push({
      id: `resp-${ts}-4`,
      role: "assistant",
      content: `🪣 **Resource Agent** xác nhận:\n✅ Tank 82% — đủ nước cho 2 phiên tưới (450L)\n✅ PUMP_01 hoạt động bình thường\n✅ pH nước: 6.8 (tối ưu cho cây trồng)`,
      timestamp: ts + 3000,
      agent_name: "ResourceAgent",
      data_sources: ["TANK_01", "PUMP_01", "PH_01"],
    });

    responses.push({
      id: `resp-${ts}-5`,
      role: "assistant",
      content: `⚡ **Farm Action Agent** đã thực hiện:\n\n✅ **Tool:** \`createIrrigationSchedule()\` → 200 OK\n✅ **Verification:** Đọc lại lịch → Lịch tưới đã tồn tại trong hệ thống\n\n📋 Kế hoạch chờ **phê duyệt** của bạn. Nhấn nút Phê duyệt ở tab Dashboard.`,
      timestamp: ts + 4000,
      agent_name: "FarmActionAgent",
    });
  } else {
    responses.push({
      id: `resp-${ts}-3`,
      role: "assistant",
      content: `🧠 **Farm Coordinator** tổng hợp:\n\nHệ thống nông trại đang hoạt động ổn định:\n• 6/6 thiết bị đang online\n• Không có cảnh báo nghiêm trọng\n• Kế hoạch tưới tiếp theo: 17:30 hôm nay\n\nBạn có thể hỏi tôi về:\n• Lập kế hoạch tưới\n• Kiểm tra phiên tưới\n• Tình trạng thiết bị\n• Báo cáo canh tác`,
      timestamp: ts + 2000,
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
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  // Cleanup SSE stream on unmount
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
    };
  }, []);

  /**
   * Send message — tries real agent-core API first, falls back to mock.
   */
  const handleSend = async (text?: string) => {
    const messageText = text || input.trim();
    if (!messageText || isTyping) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: messageText,
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);
    setCurrentPhase("Đang kết nối Agent-Core...");

    try {
      // Step 1: Create agent session via web-backend proxy
      const createRes = await fetch("http://localhost:8000/api/v1/agent/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_request: messageText }),
      });

      if (!createRes.ok) {
        throw new Error(`HTTP ${createRes.status}`);
      }

      const { session_id } = await createRes.json();

      // Show session created message
      setMessages((prev) => [
        ...prev,
        {
          id: `session-${session_id}`,
          role: "assistant",
          content: `🚀 **Phiên Multi-Agent** \`${session_id}\` đã được tạo. Đang xử lý...`,
          timestamp: Date.now(),
          agent_name: "System",
        },
      ]);

      // Step 2: Subscribe to SSE stream for real-time agent events
      const abortController = new AbortController();
      abortRef.current = abortController;

      const sseRes = await fetch(
        `http://localhost:8000/api/v1/agent/sessions/${session_id}/stream`,
        { signal: abortController.signal }
      );

      if (!sseRes.ok || !sseRes.body) {
        throw new Error("SSE stream failed");
      }

      const reader = sseRes.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // Read SSE stream
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        let currentEvent = "";
        let currentData = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            currentData = line.slice(6).trim();
          } else if (line === "" && currentData) {
            // End of SSE event — process it
            try {
              if (currentEvent === "agent_event") {
                const event = JSON.parse(currentData);
                const icon = AGENT_ICONS[event.agent_name] || "🤖";
                const phaseLabel = PHASE_LABELS[event.phase] || event.phase;
                setCurrentPhase(`${icon} ${event.agent_name}: ${phaseLabel}`);

                const chatMsg: ChatMessage = {
                  id: `agent-${session_id}-${event.sequence}`,
                  role: "assistant",
                  content: `${icon} **${event.agent_name} Agent** (${phaseLabel}):\n${event.result_summary}${
                    event.duration_ms > 0 ? `\n⏱️ ${event.duration_ms}ms` : ""
                  }${
                    event.llm_call
                      ? `\n🧠 LLM: ${event.llm_call.model} (${event.llm_call.prompt_tokens}→${event.llm_call.completion_tokens} tokens)`
                      : ""
                  }`,
                  timestamp: Date.now(),
                  agent_name: event.agent_name,
                };
                setMessages((prev) => [...prev, chatMsg]);
              } else if (currentEvent === "session_complete") {
                // Fetch final session state for narrative
                try {
                  const finalRes = await fetch(
                    `http://localhost:8000/api/v1/agent/sessions/${session_id}`
                  );
                  if (finalRes.ok) {
                    const finalData = await finalRes.json();
                    if (finalData.narrative_text) {
                      setMessages((prev) => [
                        ...prev,
                        {
                          id: `narrative-${session_id}`,
                          role: "assistant",
                          content: `📝 **Báo cáo tổng hợp:**\n\n${finalData.narrative_text}`,
                          timestamp: Date.now(),
                          agent_name: "Narrative",
                        },
                      ]);
                    }
                    setMessages((prev) => [
                      ...prev,
                      {
                        id: `done-${session_id}`,
                        role: "assistant",
                        content: `✅ Phiên **${session_id}** hoàn tất — Trạng thái: **${finalData.state}**${
                          finalData.action_plan_id
                            ? `\n📋 Kế hoạch: \`${finalData.action_plan_id}\``
                            : ""
                        }${
                          finalData.verification_verdict
                            ? `\n🔍 Xác minh: **${finalData.verification_verdict}**`
                            : ""
                        }`,
                        timestamp: Date.now(),
                        agent_name: "System",
                      },
                    ]);
                  }
                } catch {
                  // Ignore — session complete is enough
                }
              }
            } catch {
              // Skip malformed SSE data
            }
            currentEvent = "";
            currentData = "";
          }
        }
      }
    } catch (err: any) {
      // Fallback to mock responses when agent-core is unavailable
      console.warn("Agent-core unavailable, using mock:", err?.message);

      setMessages((prev) => [
        ...prev,
        {
          id: `fallback-notice-${Date.now()}`,
          role: "assistant",
          content: "⚠️ *Agent-Core offline — chuyển sang chế độ demo*",
          timestamp: Date.now(),
          agent_name: "System",
        },
      ]);

      const responses = generateFallbackResponse(messageText);
      for (let i = 0; i < responses.length; i++) {
        await new Promise((resolve) => setTimeout(resolve, 800 + Math.random() * 400));
        setMessages((prev) => [...prev, responses[i]]);
      }
    } finally {
      setIsTyping(false);
      setCurrentPhase(null);
      abortRef.current = null;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-full sm:w-[400px] max-w-full z-[60] bg-white shadow-2xl border-l border-slate-200 flex flex-col transform transition-transform duration-300 slide-in-right">
      {/* Chat Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-white">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-emerald-100 flex items-center justify-center">
            <Bot className="w-5 h-5 text-emerald-600" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-800">Farm AI Assistant</h2>
            <p className="text-[10px] text-emerald-600 font-mono">Multi-Agent Coordinator</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-full bg-slate-50 flex items-center justify-center hover:bg-slate-100 transition"
        >
          <X className="w-4 h-4 text-slate-500" />
        </button>
      </div>

      {/* Quick Actions */}
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/50 overflow-x-auto">
        <div className="flex gap-2">
          {QUICK_ACTIONS.map((action, i) => (
            <button
              key={i}
              onClick={() => handleSend(action.prompt)}
              disabled={isTyping}
              className="flex-shrink-0 text-xs px-3 py-1.5 rounded-full border border-slate-200 bg-white text-slate-700 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700 transition-all whitespace-nowrap shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 bg-slate-50/30">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} fade-in-up`}>
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0 mr-2 mt-1 shadow-sm">
                <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
              </div>
            )}
            <div className={`px-4 py-2.5 max-w-[85%] text-sm ${
              msg.role === "user" 
                ? "bg-emerald-600 text-white rounded-2xl rounded-tr-sm shadow-sm" 
                : "bg-white border border-slate-100 text-slate-700 rounded-2xl rounded-tl-sm shadow-sm"
            }`}>
              {/* Agent name tag */}
              {msg.agent_name && (
                <span className="text-[10px] text-emerald-600 font-mono font-semibold block mb-1">
                  {AGENT_ICONS[msg.agent_name] || "🤖"} {msg.agent_name}
                </span>
              )}
              {/* Render content with basic markdown-like formatting */}
              <div className="whitespace-pre-wrap leading-relaxed">
                {msg.content.split(/(\*\*.*?\*\*|`.*?`)/g).map((part, i) => {
                  if (part.startsWith("**") && part.endsWith("**")) {
                    return <strong key={i} className={msg.role === "user" ? "font-semibold text-white" : "font-semibold text-slate-900"}>{part.slice(2, -2)}</strong>;
                  }
                  if (part.startsWith("`") && part.endsWith("`")) {
                    return <code key={i} className={`px-1 rounded text-xs font-mono ${msg.role === "user" ? "bg-emerald-700 text-emerald-100" : "bg-slate-100 text-emerald-700 border border-slate-200"}`}>{part.slice(1, -1)}</code>;
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
                      className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200"
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
          <div className="flex items-center gap-2 text-slate-500 text-sm fade-in-up">
            <div className="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0 shadow-sm">
              <Loader2 className="w-3.5 h-3.5 text-emerald-600 animate-spin" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-mono">
                {currentPhase || "Agent đang xử lý..."}
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-slate-100 bg-white" style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}>
        <div className="flex items-center gap-2 bg-slate-50 rounded-2xl border border-slate-200 px-4 py-2 focus-within:border-emerald-400 focus-within:bg-white transition-colors shadow-inner">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Hỏi AI về nông trại..."
            className="flex-1 bg-transparent outline-none text-sm text-slate-800 placeholder-slate-400"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isTyping}
            className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center hover:bg-emerald-200 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4 text-emerald-600" />
          </button>
        </div>
      </div>
    </div>
  );
}
