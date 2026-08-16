# 04 — Hướng dẫn tích hợp

> Đọc file này + [03-contracts.md](03-contracts.md) là đủ để bắt đầu code, không cần đọc gì thêm.

---

## 0. TL;DR cho từng người

| Bạn phụ trách | Việc phải làm | Mất bao lâu |
|---|---|---|
| **Data / Stream** | Sửa bug `temp_avg` đang chặn `topic_p`/`topic_h` (§1) | 5 phút — **làm trước tiên** |
| **Web Backend** | Thêm 5 topic vào `subscribe`, thêm 5 WS event, proxy SSE (§2) | ~1 giờ |
| **Web Frontend** | Nghe WS event mới, dựng panel trace + phê duyệt + evidence (§3) | ~3 giờ |
| **Database** | Thêm 5 bảng (§4) | ~40 phút |
| **Mình (agent-core)** | Viết service | phiên sau |

---

## 1. Việc của Data / Stream Engine

### 1.1 🔴 BUG ĐANG CHẶN TOÀN BỘ PIPELINE

[`services/ingestion-stream-engine/src/processor.py:79`](../../services/ingestion-stream-engine/src/processor.py#L79):

```python
logger.info(f"[WINDOW CLOSED: {win_type}] Station: {station_id} | Temp: {agg['metrics']['temp_avg']}°C | Anomalies: {len(anomalies)}")
```

**Vì sao hỏng:** thiết bị Track B gửi field `temperature`, không phải `temp`. `aggregate_window_records()` sinh key theo `f"{key}_avg"` → ra `temperature_avg`. Key `temp_avg` **không tồn tại** với bất kỳ thiết bị nào trong 6 thiết bị.

**Hậu quả:** `KeyError` ném ra ở dòng log này, tức là **trước** `producer.send()` bên dưới. Exception bị bắt ở `run()` và chỉ log ra "Error processing record". Kết quả: **không một window nào được publish lên `topic_p` hay `topic_h`.** Tầng AI đang đói dữ liệu hoàn toàn, và triệu chứng bề mặt chỉ là vài dòng log lỗi trông vô hại.

Ngoài ra `SOIL_01` và `WEATHER_01` đều có `temperature_avg` nhưng ý nghĩa khác nhau (nhiệt độ đất vs nhiệt độ không khí) — nên log một field cố định cho mọi thiết bị vốn đã không hợp lý.

**Cách sửa** — log không phụ thuộc thiết bị:

```python
metrics = agg.get("metrics", {})
preview = ", ".join(f"{k}={v}" for k, v in list(metrics.items())[:3]) or "(no metrics)"
logger.info(f"[WINDOW CLOSED: {win_type}] Device: {station_id} | {preview} | Anomalies: {len(anomalies)}")
```

**Kiểm chứng đã sửa xong:**
```bash
python farm_simulator.py          # terminal 1
python services/ingestion-stream-engine/main.py   # terminal 2
```
Sau ~60 giây phải thấy log `⚡ [PUBLISHED -> topic_p]`. Nếu chưa thấy thì chưa xong.

### 1.2 `topic_alerts` luôn rỗng

`aggregate_window_records()` không sinh field `anomalies`, nên `agg.get("anomalies", [])` ở [processor.py:77](../../services/ingestion-stream-engine/src/processor.py#L77) luôn là `[]` và nhánh publish alert không bao giờ chạy.

Không chặn `agent-core` (mình tự phát hiện bất thường ở lớp ML riêng), nhưng nếu UI đang đợi `topic_alerts` thì sẽ đợi mãi. Hai lựa chọn: cho aggregator sinh `anomalies`, hoặc bỏ topic đó và dùng `topic_agent_events` của mình.

### 1.3 Cam kết mình cần từ tầng stream

- `topic_raw` giữ nguyên payload gốc của BTC + `event_time`, `ingestion_time`, `device_id`
- `topic_p` / `topic_h` giữ nguyên hình dạng `aggregate_window_records()` hiện tại
- **Nếu đổi tên field hay hình dạng, báo mình trước** — Farm State Store parse trực tiếp

---

## 2. Việc của Web Backend (NestJS)

### 2.1 Thêm 5 topic vào subscribe

[`src/modules/kafka/kafka.service.ts`](../../services/web-backend/src/modules/kafka/kafka.service.ts) — mảng `topics` ở dòng ~41:

```ts
const topicAgentEvents  = process.env.TOPIC_AGENT_EVENTS  || 'topic_agent_events';
const topicPlans        = process.env.TOPIC_PLANS         || 'topic_plans';
const topicTasks        = process.env.TOPIC_TASKS         || 'topic_tasks';
const topicNotifications= process.env.TOPIC_NOTIFICATIONS || 'topic_notifications';
const topicVerifications= process.env.TOPIC_VERIFICATIONS || 'topic_verifications';

await this.consumer.subscribe({
  topics: [
    topicRaw, topicP, topicH, topicAlerts, topicForecasts,
    topicAgentEvents, topicPlans, topicTasks, topicNotifications, topicVerifications,
  ],
  fromBeginning: false,
});
```

Trong `eachMessage`, thêm 5 nhánh — giữ nguyên phong cách hiện có:

```ts
else if (topic === topicAgentEvents)  this.eventsGateway.broadcast('AGENT_EVENT', payload);
else if (topic === topicPlans)        this.eventsGateway.broadcast('PLAN_CREATED', payload);
else if (topic === topicTasks)        this.eventsGateway.broadcast('TASK_CREATED', payload);
else if (topic === topicNotifications)this.eventsGateway.broadcast('NOTIFICATION', payload);
else if (topic === topicVerifications)this.eventsGateway.broadcast('VERIFICATION', payload);
```

### 2.2 Proxy sang agent-core

Frontend chỉ nên biết một origin. Thêm controller proxy tới `http://agent-core:8100`:

| Route NestJS | Chuyển tới | Ghi chú |
|---|---|---|
| `POST /api/v1/agent/sessions` | `POST :8100/api/v1/agent/sessions` | |
| `GET /api/v1/agent/sessions/:id/stream` | `GET :8100/.../stream` | **SSE — phải stream, không buffer** |
| `GET /api/v1/agent/sessions/:id` | idem | |
| `POST /api/v1/approvals/:id` | idem | |
| `GET /api/v1/plans` · `/tasks` · `/approvals` · `/state/farm` | idem | |

Lưu ý SSE: đặt `res.setHeader('Content-Type','text/event-stream')`, `'Cache-Control','no-cache'`, `'Connection','keep-alive'`, và **tắt compression** cho route này. Nếu ngại xử lý SSE, phương án dự phòng: frontend gọi thẳng `:8100` và backend chỉ lo WebSocket — trace vẫn tới UI qua `AGENT_EVENT`, vì hai đường phát cùng một payload.

### 2.3 Biến env thêm vào `docker-compose.yml`

```yaml
web-backend:
  environment:
    - TOPIC_AGENT_EVENTS=topic_agent_events
    - TOPIC_PLANS=topic_plans
    - TOPIC_TASKS=topic_tasks
    - TOPIC_NOTIFICATIONS=topic_notifications
    - TOPIC_VERIFICATIONS=topic_verifications
    - AGENT_CORE_URL=http://agent-core:8100
```

---

## 3. Việc của Web Frontend (Next.js)

### 3.1 Event WebSocket mới

| Event | Payload | Dùng để |
|---|---|---|
| `AGENT_EVENT` | [`AgentEvent`](03-contracts.md#31-agentevent--topic_agent_events) | Vẽ trace agent live |
| `PLAN_CREATED` | `IrrigationPlan` | Thêm vào danh sách kế hoạch |
| `TASK_CREATED` | `InspectionTicket` | Thêm vào danh sách nhiệm vụ |
| `NOTIFICATION` | `Notification` | Toast / chuông |
| `VERIFICATION` | `VerificationResult` | Đóng dấu ✅ lên hành động tương ứng |

### 3.2 Bốn khối UI mà BTC chấm điểm

BTC liệt kê rõ yêu cầu UX. Bốn khối này map 1-1:

**a) Panel trace Agent** — *"Hiển thị kế hoạch, nhiệm vụ và người/Agent chịu trách nhiệm"*
Timeline dựng từ `AGENT_EVENT`, sắp theo `seq`. Mỗi dòng hiện `agent`, `title_vi`, `detail_vi`, thời gian.
→ Dùng `llm_call.used` để phân biệt trực quan **bước do AI quyết** và **bước do code gác**. Đây là chi tiết ăn điểm khi phản biện.

**b) Evidence dưới mỗi quyết định** — *"Thể hiện rõ dữ liệu IoT đã ảnh hưởng đến quyết định nào"*
Từ `GET /api/v1/agent/sessions/{id}`: mỗi phần tử `decisions[]` có `evidence_refs[]`; nối sang `evidence_ledger[]` theo `evidence_id`. Hiện dạng chip bấm được: `SOIL_01 · 31.4% · 12s trước`.
→ Đây gần như là khối quan trọng nhất cho điểm UX. Đừng bỏ.

**c) Khu phê duyệt** — *"Có khu vực phê duyệt kế hoạch hoặc hành động quan trọng"*
Poll `GET /api/v1/approvals?status=PENDING` hoặc bắt `AGENT_EVENT` có `status: AWAITING_APPROVAL`. Hai nút → `POST /api/v1/approvals/{id}`.

**d) Chỉ báo kết nối & độ mới** — *"Hiển thị trạng thái kết nối và độ mới của dữ liệu"*
Poll `GET /health` (5s/lần) + `GET /api/v1/state/farm`. Hiện 6 chấm thiết bị: xanh `FRESH` / vàng `STALE` / xám `OFFLINE`, kèm `age_seconds`.

### 3.3 Lưu ý về độ trễ

Model local mất **15–40 giây** cho một phiên. Đừng dùng spinner chờ — dùng trace stream, mỗi `AgentEvent` tới là một dòng mới. Thời gian chờ trở thành nội dung xem được, và nó cũng chính là thứ chứng minh hệ thống đang thực sự phối hợp nhiều agent.

Yêu cầu responsive điện thoại/tablet của BTC áp dụng cho cả 4 khối trên.

---

## 4. Việc của Database Saver

Thêm vào [`services/database-saver/db.py`](../../services/database-saver/db.py), theo đúng phong cách `_init_tables()` hiện có:

```sql
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id TEXT PRIMARY KEY,
    user_request TEXT NOT NULL,
    playbook TEXT,
    status TEXT,
    mode TEXT,
    data_completeness TEXT,
    narrative TEXT,          -- JSON
    timing TEXT,             -- JSON
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_ledger (
    evidence_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value_text TEXT,
    unit TEXT,
    observed_at REAL,
    age_seconds REAL,
    freshness TEXT,
    source_topic TEXT,
    window_type TEXT,
    is_absence_record INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS irrigation_plans (
    schedule_id TEXT PRIMARY KEY,
    session_id TEXT,
    zone TEXT,
    start_time TEXT,
    duration_minutes INTEGER,
    target_volume_liters REAL,
    priority TEXT,
    status TEXT,
    reason_vi TEXT,
    confidence TEXT,
    mode TEXT,
    evidence_refs TEXT,      -- JSON array
    approval_id TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS inspection_tasks (
    ticket_id TEXT PRIMARY KEY,
    session_id TEXT,
    device_id TEXT,
    issue_type TEXT,
    priority TEXT,
    status TEXT,
    description_vi TEXT,
    assignee_staff_id TEXT,
    evidence_refs TEXT,      -- JSON array
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS verifications (
    verification_id TEXT PRIMARY KEY,
    session_id TEXT,
    object_type TEXT,
    object_id TEXT,
    verdict TEXT,
    read_back_ok INTEGER,
    field_matches INTEGER,
    field_mismatches INTEGER,
    differences TEXT,        -- JSON
    evidence_audit TEXT,     -- JSON
    retry_count INTEGER,
    message_vi TEXT,
    verified_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_evidence_session ON evidence_ledger(session_id);
CREATE INDEX IF NOT EXISTS idx_plans_session    ON irrigation_plans(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_device     ON inspection_tasks(device_id);
```

Rồi subscribe 5 topic mới trong `main.py` và ghi tương ứng, giống cách `save_forecast()` đang làm.

> `evidence_ledger` là bảng đáng giá nhất khi phản biện: nó là bằng chứng kiểm toán được rằng mỗi quyết định đều truy được về một số đo cụ thể, tại một thời điểm cụ thể, từ một thiết bị cụ thể.

---

## 5. Setup LM Studio

### 5.1 Cài & chạy

1. Cài LM Studio (https://lmstudio.ai)
2. Tab **Discover** → tìm `qwen2.5-3b-instruct` → tải bản GGUF (khuyến nghị `Q4_K_M`: ~2GB, đủ chất lượng, chạy được trên máy không GPU rời)
3. Tab **Developer** (hoặc **Local Server**) → chọn model → **Start Server**
4. ⚠️ **Đặt Context Length ≥ 8192.** Mặc định thường là 4096 — Farm State Digest + prompt sẽ bị cắt cụt và agent trả lời sai một cách khó đoán. Đây là lỗi cấu hình tốn nhiều thời gian nhất.
5. Bật **Structured Output / JSON Schema** nếu có toggle riêng

### 5.2 Kiểm chứng

```bash
curl http://localhost:1234/v1/models
```
Phải thấy `qwen2.5-3b-instruct` trong danh sách.

```bash
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-3b-instruct",
    "messages": [{"role":"user","content":"Trả về JSON: {\"ok\": true}"}],
    "temperature": 0.1
  }'
```

### 5.3 Chạy trong Docker

Container không thấy `localhost` của máy host. Trong `docker-compose.yml`:

```yaml
agent-core:
  environment:
    - LOCAL_LLM_BASE_URL=http://host.docker.internal:1234/v1
  extra_hosts:
    - "host.docker.internal:host-gateway"
```

Trên Windows/macOS `host.docker.internal` có sẵn; trên Linux cần dòng `extra_hosts` ở trên.

---

## 6. Đổi sang Gemini

Cả LM Studio và Gemini đều nói giao thức OpenAI. Đổi **một** biến:

```env
LLM_PROFILE=gemini
GEMINI_LLM_API_KEY=AIza...        # điền key thật
```

Không sửa dòng code nào. Chi tiết & đánh đổi: [ADR-001](adr/ADR-001-llm-provider-strategy.md).

**Trước khi chuyển, chạy bộ eval** ([08-eval-harness.md](08-eval-harness.md)) dưới cả hai profile — quyết định bằng số, và bảng so sánh đó là vật liệu phản biện tốt.

> ⚠️ `GEMINI_API_KEY` hiện có trong `.env` (`AQ.Ab8RN6Lda5OD...`) **không đúng định dạng Gemini API key** — key thật bắt đầu bằng `AIza`. Chuỗi này trông giống OAuth token. Cần lấy key mới từ Google AI Studio trước khi dùng profile `gemini`.

---

## 7. Cấu hình `agent-core`

File `services/agent-core/.env.example` — copy thành `.env` để chạy local.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LLM_PROFILE` | `local` | `local` \| `gemini` — **đổi provider bằng dòng này** |
| `LOCAL_LLM_BASE_URL` | `http://localhost:1234/v1` | Endpoint LM Studio |
| `LOCAL_LLM_MODEL` | `qwen2.5-3b-instruct` | |
| `LOCAL_MAX_DISPATCH_ROUNDS` | `2` | Chặn vòng orchestrator ở profile local |
| `GEMINI_LLM_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | Lớp OpenAI-compat của Gemini |
| `GEMINI_MAX_DISPATCH_ROUNDS` | `4` | Model mạnh hơn → được nới |
| `LLM_TEMPERATURE_DECISION` | `0.1` | Cho call quyết định |
| `LLM_TEMPERATURE_NARRATIVE` | `0.6` | Cho call viết văn |
| `FRESHNESS_FRESH_SEC` | `60` | Ngưỡng `FRESH` |
| `FRESHNESS_STALE_SEC` | `600` | Trên ngưỡng này là `OFFLINE` |
| `POLICY_MIN_TANK_LEVEL_PCT` | `20` | Dưới mức này chặn tưới |
| `POLICY_APPROVAL_THRESHOLD_LITERS` | `500` | Trên mức này cần người duyệt |
| `AGENT_CORE_PORT` | `8100` | |

---

## 8. Thứ tự khởi động khi demo

```
1. LM Studio  → Start Server (kiểm: curl :1234/v1/models)
2. docker compose up -d redpanda mosquitto
3. docker compose up -d stream-engine database-saver
4. python farm_simulator.py          (hoặc chờ MQTT thật của BTC)
5. Kiểm: Redpanda Console :8088 → topic_p PHẢI có message
6. docker compose up -d agent-core   (kiểm: curl :8100/health)
7. docker compose up -d web-backend web-frontend
8. Mở :3000
```

**Bước 5 là cổng kiểm quan trọng nhất.** Nếu `topic_p` rỗng thì bug ở §1.1 chưa được sửa, và mọi thứ phía sau sẽ chạy nhưng không có dữ liệu. Đừng bỏ qua bước này khi tổng duyệt.

---

## 9. Cam kết hai chiều

**Mình cam kết:**
- Không sửa file ngoài `services/agent-core/` và `docs/agent-core/`
- Payload đúng như [03-contracts.md](03-contracts.md); đổi thì báo trước và bump `schema_version`
- `GET /health` luôn trả về được, kể cả khi LLM chết (`llm_reachable: false`)

**Mình cần:**
- `topic_p`/`topic_h` thực sự có dữ liệu (§1.1)
- Hình dạng `topic_raw` không đổi tên field mà không báo
- Cổng `8100` không bị service khác chiếm
