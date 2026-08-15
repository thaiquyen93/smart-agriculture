# 🌾 SMURF PLATFORM - SMART AGRICULTURE IOT & MULTI-AGENT AI
## Dự án SEAL Hackathon Summer 2026 (Track B: Smart Agriculture)

> **Tài liệu Hướng dẫn Vận hành & Phân công Công việc cho 5 Thành viên trong Đội thi**

---

## 🏛️ TỔNG QUAN HỆ THỐNG VÀ BẢN ĐỒ PHÂN CÔNG (MICROSERVICES)

```text
Smurf/
├── docker-compose.yml              # Dựng trọn bộ 5 Microservices + Redpanda + MQTT
├── .env                            # File cấu hình chung cho cả đội
│
├── services/
│   ├── ingestion-stream-engine/    # 🔴 KHU VỰC 1: DATA ENGINEER & STREAM PROCESSING 
│   ├── ai-agent/                   # 🟢 KHU VỰC 2: MULTI-AGENT AI CORE (TEAM AI)
│   ├── web-backend/                # 🔵 KHU VỰC 3: NESTJS BACKEND (TEAM WEB BACKEND)
│   ├── web-frontend/               # 🟡 KHU VỰC 4: NEXT.JS CONTROL ROOM UI (TEAM WEB FRONTEND)
│   └── database-saver/             # 🟣 KHU VỰC 5: HISTORICAL DATABASE PERSISTENCE (LƯU DB)
│
└── simulator/                      # Bộ giả lập IoT để test offline
```

---

## 🔴 KHU VỰC 1: HƯỚNG DẪN CHO DATA (DATA & STREAM ENGINE)

### 📂 Thư mục làm việc: `services/ingestion-stream-engine/`

#### 🎯 Nhiệm vụ của bạn:
1. Hứng dữ liệu cảm biến Đất & Khí hậu từ MQTT của Ban Tổ Chức (BTC).
2. Chạy **Watermarking** (lùi đồng hồ 5s chờ data trễ) và **Windowing** (gom 1 phút & 1 giờ).
3. Đẩy dữ liệu thô và dữ liệu đã gom vào các Redpanda Topics cho Team AI và Team Web dùng.

#### 🚀 Cách chạy khu vực của bạn:
1. Mở file `.env` tại thư mục gốc `Smurf/`, điền thông số BTC cấp vào:
   ```env
   MQTT_BROKER_HOST=192.168.x.x   # IP MQTT BTC
   MQTT_BROKER_PORT=1883
   MQTT_TOPIC_WEATHER=contest/iot/#
   ```
2. Mở Terminal tại thư mục `services/ingestion-stream-engine/`:
   ```bash
   pip install -r requirements.txt
   python main.py
   ```
3. Mở trình duyệt vào `http://localhost:8088` (Redpanda Console) để kiểm tra data chảy vào `topic_raw`, `topic_p`, `topic_h`.

---

## 🟢 KHU VỰC 2: HƯỚNG DẪN CHO TEAM AI (MULTI-AGENT AI CORE)

### 📂 Thư mục làm việc: `services/ai-agent/`

#### 🎯 Nhiệm vụ của Team AI:
1. Đọc dữ liệu gom 1 phút (`topic_p`) và 1 giờ (`topic_h`) từ Redpanda.
2. Viết thuật toán đánh giá tập mờ **Fuzzy Logic** và **Model Dự báo**.
3. Gọi **Gemini 2.5 Flash API** để viết bản tin chỉ đạo nông nghiệp (Tưới nước, pha phân bón, ngập úng).

#### 🚀 Cách chạy khu vực Team AI:
1. Mở Terminal tại thư mục `services/ai-agent/`:
   ```bash
   pip install -r requirements.txt
   ```
2. **Nơi Team AI viết code:**
   - **Fuzzy Logic:** Sửa file `src/fuzzy_engine.py` (chỉnh các hàm mờ độ ẩm đất, nhiệt độ).
   - **Model Dự báo:** Sửa file `src/predict_agent.py` (load model `.pkl` nếu có).
   - **Gemini LLM:** Sửa file `src/gemini_rewriter.py` (chỉnh Prompt chỉ đạo nông nghiệp).
3. **Chạy thử nghiệm AI:**
   ```bash
   python main.py
   ```
   *Kết quả AI sẽ tự động bắn vào Redpanda `topic_forecasts` và `topic_alerts`!*

---

## 🔵 KHU VỰC 3: HƯỚNG DẪN CHO TEAM WEB BACKEND (NESTJS BACKEND)

### 📂 Thư mục làm việc: `services/web-backend/`

#### 🎯 Nhiệm vụ của Web Backend:
1. Lắng nghe toàn bộ Redpanda Topics (`topic_raw`, `topic_p`, `topic_h`, `topic_alerts`, `topic_forecasts`).
2. Phát dữ liệu Real-time qua **WebSocket (`ws://localhost:8000/ws`)** lên Frontend.
3. Cung cấp các đường REST API (`/api/v1/health`, `/api/v1/telemetry/latest`).

#### 🚀 Cách chạy khu vực Web Backend:
1. Mở Terminal tại thư mục `services/web-backend/`:
   ```bash
   npm install
   ```
2. **Nơi Web Backend viết code (Modular NestJS):**
   - `src/modules/kafka/kafka.service.ts`: Nơi nhận dữ liệu từ Redpanda.
   - `src/modules/websocket/events.gateway.ts`: Nơi quản lý cổng WebSocket.
   - `src/modules/telemetry/telemetry.controller.ts`: Nơi tạo các đường REST API.
3. **Chạy thử nghiệm Backend:**
   ```bash
   npm run start:dev
   ```
   *Server Backend sẽ bật tại: `http://localhost:8000` (WebSocket tại `ws://localhost:8000/ws`)*

---

## 🟡 KHU VỰC 4: HƯỚNG DẪN CHO TEAM WEB FRONTEND (NEXT.JS CONTROL ROOM)

### 📂 Thư mục làm việc: `services/web-frontend/`

#### 🎯 Nhiệm vụ của Web Frontend:
1. Lắng nghe WebSocket real-time từ Backend (`ws://localhost:8000/ws`).
2. Vẽ giao diện **Smart Agriculture Control Room Dashboard** (Dark Mode).
3. Hiển thị thông số Đất/Khí hậu real-time và các **Thẻ hành động tưới tiêu thông minh của Gemini AI**.

#### 🚀 Cách chạy khu vực Web Frontend:
1. Mở Terminal tại thư mục `services/web-frontend/`:
   ```bash
   npm install
   ```
2. **Nơi Web Frontend viết code (Next.js 14 + React + Tailwind):**
   - `src/app/page.tsx`: Giao diện Dashboard chính.
   - `src/app/globals.css`: Cấu hình màu sắc CSS Dark Mode.
3. **Chạy thử nghiệm Frontend:**
   ```bash
   npm run dev
   ```
   *Mở trình duyệt xem giao diện tại: `http://localhost:3000`*

---

## 🟣 KHU VỰC 5: HISTORICAL DATABASE PERSISTENCE (LƯU DB LỊCH SỬ)

### 📂 Thư mục làm việc: `services/database-saver/`

#### 🎯 Nhiệm vụ:
Lắng nghe toàn bộ Redpanda Topics và tự động ghi bền vững dữ liệu lịch sử vào file SQLite `data/smurf_database.sqlite`.

#### 🚀 Cách chạy:
```bash
cd services/database-saver
pip install -r requirements.txt
python main.py
```

---

## 🏆 CÁCH KHỞI ĐỘNG TRỌN BỘ HỆ THỐNG CHO BUỔI DEMO / CHẤM THI

Khi đến giờ trình diễn trước Ban Giám Khảo, mở Terminal tại thư mục gốc `Smurf/` và gõ 1 lệnh duy nhất:

```bash
docker compose up --build -d
```

Toàn bộ 5 Vi dịch vụ + Redpanda Broker + Mosquitto MQTT sẽ tự động kết nối và vận hành hoàn hảo trên máy đi thi! 🚀🏆✨
