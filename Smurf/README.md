# 🚀 SMURF - ENTERPRISE REAL-TIME IOT & STREAM PROCESSING PLATFORM
## SEAL Hackathon Summer 2026

---

## 🏛️ KIẾN TRÚC VI DỊCH VỤ (MICROSERVICES ARCHITECTURE)

```text
Smurf/
├── docker-compose.yml              # Complete Container Orchestration
├── .env                            # Environment Configuration
│
├── services/
│   ├── ingestion-stream-engine/    # Python Stream Processing Engine & MQTT Bridge
│   │   ├── src/config.py           # Flexible BTC MQTT & Redpanda Config
│   │   ├── src/mqtt_bridge.py      # MQTT Ingestion Bridge -> topic_raw
│   │   ├── src/watermark.py        # Watermarking Engine (Bounded 5s Delay)
│   │   ├── src/windowing.py        # Tumbling 1m + Sliding 5m + Hourly 1h
│   │   ├── src/aggregators.py      # Heat Index, Dew Point, Anomaly Rules
│   │   └── src/processor.py        # Main Loop -> TOPIC_P (1m) & TOPIC_H (1h)
│   │
│   └── web-backend/                # TypeScript Node.js Express + WebSockets Backend
│       ├── package.json
│       ├── tsconfig.json
│       └── src/server.ts           # TS Express Server + KafkaJS Consumer
│
└── simulator/                      # Mock IoT Weather Simulator (for offline testing)
    └── main.py
```

---

## 📡 REDPANDA TOPICS SUMMARY

| Topic Name | Frequency | Target Consumers | Description |
|---|---|---|---|
| **`topic_raw`** | 2s tick | Stream Engine, Isolation Forest | Raw IoT telemetry stream straight from MQTT |
| **`topic_p`** | 1 min slide | Fuzzy Logic Engine, Predict Agent | 1-minute Tumbling & 5-minute Sliding window aggregations |
| **`topic_h`** | 1 hour | Gemini LLM, Macro RAG | 1-hour macro window aggregations (total rain, heat stress) |
| **`topic_alerts`** | Event-driven | Web Backend, Notification Bot | Severe anomaly alerts & emergency actions |
| **`topic_forecasts`** | Event-driven | Web Backend | AI-generated forecasts and risk assessments |

---

## ⚡ HƯỚNG DẪN BẮT ĐẦU CHO CÁC THÀNH VIÊN TEAM (QUICKSTART)

### 1️⃣ Khi BTC công bố thông số MQTT (Ngày mai)
Mở file `.env` và cập nhật 3 dòng:
```env
MQTT_BROKER_HOST=192.168.x.x  # IP MQTT BTC cho
MQTT_BROKER_PORT=1883
MQTT_TOPIC_WEATHER=contest/iot/#
```

### 2️⃣ Khởi chạy toàn bộ hệ thống bằng Docker
```bash
docker compose up --build -d
```

### 3️⃣ Kiểm tra Dữ liệu & Console
* **Redpanda Console UI:** mở `http://localhost:8088` xem data chảy qua các topics.
* **TypeScript Backend API:** mở `http://localhost:8000/api/v1/health`.
* **WebSocket Live Stream:** `ws://localhost:8000`
