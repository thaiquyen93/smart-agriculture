# 03 — Hợp đồng dữ liệu (Contracts)

> **Đây là file các thành viên khác cần.** Mọi thứ ở đây là cam kết: `agent-core` sẽ phát ra đúng hình dạng này. Code được từ hôm nay, không cần chờ mình viết xong service.

---

## 1. Quy tắc "tập giao schema" — BẮT BUỘC

> Áp dụng cho **schema đưa vào `response_format` của LLM**. Schema của Kafka event (§3) chỉ là tài liệu cho người, không chịu ràng buộc này.

LM Studio ép schema qua GBNF (llama.cpp); Gemini ép qua `responseSchema`. Cả hai đều là **tập con của JSON Schema, nhưng tập con khác nhau**. Viết schema mà chỉ một bên chấp nhận thì lúc đổi provider sẽ vỡ.

**Luật:**

| ✅ Được dùng | ❌ Cấm |
|---|---|
| `type`: object, array, string, number, integer, boolean | `$ref`, `$defs`, `definitions` |
| `properties` với object **phẳng** (lồng tối đa 2 tầng) | `anyOf`, `oneOf`, `allOf`, `not` |
| `required` liệt kê **tường minh** mọi field | `patternProperties`, `additionalItems` |
| `additionalProperties: false` trên **mọi** object | `if`/`then`/`else` |
| `enum` string cho mọi tập giá trị đóng | Union kiểu (`type: ["string","null"]`) |
| `items` **một** kiểu duy nhất cho array | Tuple typing |
| `description` trên từng field | `format` phức tạp (`date-time` → dùng `string` + mô tả) |

**Cần biểu diễn "có thể vắng mặt"?** Không dùng union. Dùng một trong hai:
- field `enum` có giá trị `"NONE"` / `"UNKNOWN"`
- một field `boolean` đi kèm (`has_forecast` + `forecast_value`)

**Cách kiểm:** xem [08-eval-harness.md](08-eval-harness.md) — có bước lint schema chạy được trên cả hai provider.

---

## 2. Kafka Topics

### 2.1 `agent-core` **consume** (không đổi gì của ai)

| Topic | Nguồn | Dùng để |
|---|---|---|
| `topic_raw` | ingestion-stream-engine | Cập nhật Farm State Store + tính độ mới dữ liệu |
| `topic_p` | ingestion-stream-engine | Cửa sổ 1 phút & trượt 10 phút → feature cho ML |
| `topic_h` | ingestion-stream-engine | Cửa sổ 1 giờ → xu hướng dài |

### 2.2 `agent-core` **produce** (topic mới, cần tạo)

| Topic | Key | Nội dung | Ai consume |
|---|---|---|---|
| `topic_agent_events` | `session_id` | Trace từng bước agent, phát **real-time** khi chạy | web-backend → WS → UI |
| `topic_plans` | `schedule_id` | Lịch tưới được tạo | web-backend, database-saver |
| `topic_tasks` | `ticket_id` | Phiếu kiểm tra hiện trường | web-backend, database-saver |
| `topic_notifications` | `notification_id` | Thông báo | web-backend, database-saver |
| `topic_verifications` | `session_id` | Kết quả xác minh sau hành động | web-backend, database-saver |

Redpanda tự tạo topic khi có message đầu tiên (`auto.create.topics.enable` mặc định bật) — không cần thao tác thủ công.

---

## 3. Schema các event

> Mọi field thời gian: **ISO-8601 có offset**, ví dụ `2026-08-16T16:30:00+07:00`.
> Mọi ID: chuỗi có tiền tố, ổn định, dùng được làm khoá.

### 3.1 `AgentEvent` → `topic_agent_events`

Event phát **liên tục trong lúc phiên chạy** — đây là thứ để UI vẽ trace agent live.

```json
{
  "event_id": "EVT-20260816-000123",
  "session_id": "SESS-20260816-0007",
  "seq": 4,
  "emitted_at_iso": "2026-08-16T15:42:11+07:00",
  "phase": "WORKER",
  "agent": "AgronomyAgent",
  "status": "SUCCEEDED",
  "title_vi": "Ước lượng nhu cầu nước khu A",
  "detail_vi": "ET0 5.8 mm/ngày, thiếu ẩm 12.6% → cần khoảng 412 L (355–470 L).",
  "tool_calls": [
    {
      "tool": "estimate_water_demand",
      "arguments_summary": "zone=ZONE_A, horizon_hours=6",
      "ok": true,
      "error_code": "",
      "duration_ms": 88
    }
  ],
  "evidence_refs": ["EV-8821", "EV-8823", "EV-8827"],
  "llm_call": {
    "used": true,
    "model": "qwen2.5-3b-instruct",
    "provider": "local",
    "duration_ms": 1840,
    "prompt_tokens": 1122,
    "completion_tokens": 186
  }
}
```

| Field | Kiểu | Ghi chú |
|---|---|---|
| `seq` | int | Tăng dần trong 1 session. UI dùng để sắp xếp, chống lệch thứ tự |
| `phase` | enum | `ROUTER` · `COORDINATOR` · `WORKER` · `ACTION` · `POLICY_GATE` · `TOOL` · `VERIFY` · `NARRATIVE` · `DONE` |
| `agent` | string | Tên agent, hoặc `""` với bước thuần code |
| `status` | enum | `STARTED` · `SUCCEEDED` · `FAILED` · `BLOCKED` · `AWAITING_APPROVAL` |
| `detail_vi` | string | Tiếng Việt, hiển thị thẳng lên UI |
| `llm_call.used` | bool | `false` ở bước tất định — **UI nên hiện rõ bước nào có AI, bước nào là code** |

> `llm_call.used` là field nhỏ nhưng đáng giá khi phản biện: nó chứng minh được ngay bước nào do AI quyết và bước nào do ràng buộc tất định gác.

---

### 3.2 `EvidenceRecord`

Không có topic riêng — nhúng trong `SessionResult` và ghi vào DB. Đây là xương sống của việc "trình bày rõ dữ liệu đã dùng".

```json
{
  "evidence_id": "EV-8821",
  "session_id": "SESS-20260816-0007",
  "device_id": "SOIL_01",
  "metric": "soil_moisture",
  "value_text": "31.4",
  "unit": "%",
  "observed_at_iso": "2026-08-16T15:41:59+07:00",
  "age_seconds": 12,
  "freshness": "FRESH",
  "source_topic": "topic_raw",
  "window_type": "NONE",
  "is_absence_record": false
}
```

| Field | Ghi chú |
|---|---|
| `value_text` | **String, không phải number.** Để biểu diễn được cả `"—"` khi thiếu dữ liệu mà không cần union kiểu |
| `window_type` | `NONE` khi lấy từ `topic_raw`; `TUMBLING_1M`/`SLIDING_10M`/`HOURLY_1H` khi từ cửa sổ gom |
| `is_absence_record` | `true` khi đây là bằng chứng về **sự vắng mặt** của dữ liệu (thiết bị OFFLINE). Dùng làm căn cứ tạo phiếu kiểm tra |

---

### 3.3 `IrrigationPlan` → `topic_plans`

```json
{
  "schedule_id": "PLAN-20260816-0001",
  "session_id": "SESS-20260816-0007",
  "zone": "ZONE_A",
  "start_time_iso": "2026-08-16T16:30:00+07:00",
  "duration_minutes": 35,
  "target_volume_liters": 412.0,
  "priority": "HIGH",
  "status": "PENDING_APPROVAL",
  "reason_vi": "Độ ẩm đất dưới ngưỡng tối ưu và dự báo tiếp tục giảm trong 2 giờ tới.",
  "confidence": "CONFIDENT",
  "data_completeness": "5/6",
  "mode": "PARTIAL",
  "evidence_refs": ["EV-8821", "EV-8823", "EV-8826", "EV-8827"],
  "created_by_agent": "FarmActionAgent",
  "approval_id": "APR-20260816-0002",
  "created_at_iso": "2026-08-16T15:42:20+07:00"
}
```

| Field | Enum |
|---|---|
| `status` | `SCHEDULED` · `PENDING_APPROVAL` · `APPROVED` · `REJECTED` · `BLOCKED` · `EXECUTED` · `CANCELLED` |
| `priority` | `LOW` · `MEDIUM` · `HIGH` · `CRITICAL` |
| `confidence` | `CONFIDENT` · `TENTATIVE` — `TENTATIVE` khi có evidence STALE |
| `mode` | `FULL` · `PARTIAL` |
| `approval_id` | `""` nếu không cần duyệt |

---

### 3.4 `InspectionTicket` → `topic_tasks`

```json
{
  "ticket_id": "TASK-20260816-0007",
  "session_id": "SESS-20260816-0007",
  "device_id": "PH_01",
  "issue_type": "SENSOR_OFFLINE",
  "priority": "HIGH",
  "status": "OPEN",
  "description_vi": "PH_01 ngừng gửi dữ liệu 812 giây. Kiểm tra nguồn điện và kết nối tại bồn chính.",
  "assignee_staff_id": "STF_02",
  "assignee_name": "Nguyễn Văn B",
  "evidence_refs": ["EV-8830"],
  "created_by_agent": "FarmActionAgent",
  "created_at_iso": "2026-08-16T15:42:22+07:00"
}
```

| Field | Enum |
|---|---|
| `issue_type` | `SENSOR_OFFLINE` · `SENSOR_DRIFT` · `PUMP_FAULT` · `LOW_TANK` · `PH_OUT_OF_RANGE` · `OTHER` |
| `status` | `OPEN` · `ASSIGNED` · `IN_PROGRESS` · `RESOLVED` · `CANCELLED` |

---

### 3.5 `Notification` → `topic_notifications`

```json
{
  "notification_id": "NTF-20260816-0011",
  "session_id": "SESS-20260816-0007",
  "audience": "MANAGER",
  "severity": "WARNING",
  "title_vi": "Cảm biến pH bồn mất kết nối",
  "body_vi": "PH_01 không gửi dữ liệu 13 phút. Đã tạo phiếu kiểm tra TASK-20260816-0007.",
  "evidence_refs": ["EV-8830"],
  "related_object_type": "INSPECTION_TICKET",
  "related_object_id": "TASK-20260816-0007",
  "created_at_iso": "2026-08-16T15:42:23+07:00"
}
```

`audience`: `MANAGER` · `FIELD_TEAM` · `AGRONOMIST` — `severity`: `INFO` · `WARNING` · `CRITICAL`

---

### 3.6 `VerificationResult` → `topic_verifications`

**Đây là event chứng minh "có verification sau hành động".** Nó phải phản ánh một lần đọc lại thật.

```json
{
  "verification_id": "VER-20260816-0003",
  "session_id": "SESS-20260816-0007",
  "object_type": "IRRIGATION_SCHEDULE",
  "object_id": "PLAN-20260816-0001",
  "verdict": "VERIFIED",
  "read_back_ok": true,
  "field_matches": 8,
  "field_mismatches": 0,
  "differences": [],
  "evidence_audit": {
    "decisions_total": 4,
    "decisions_without_evidence": 0,
    "stale_evidence_used": [],
    "offline_evidence_used": [],
    "unsourced_numbers": []
  },
  "retry_count": 0,
  "message_vi": "Đã đọc lại PLAN-20260816-0001 từ cơ sở dữ liệu. 8/8 trường khớp với ý định ban đầu. Toàn bộ 4 quyết định đều có bằng chứng dữ liệu tươi.",
  "verified_at_iso": "2026-08-16T15:42:25+07:00"
}
```

`verdict`: `VERIFIED` · `PARTIAL` · `MISMATCH` · `ESCALATED`

`differences[]`: `[{field, intended, actual}]` — rỗng khi khớp.

---

### 3.7 `ApprovalRequest`

Phát trên `topic_agent_events` với `status: AWAITING_APPROVAL`, và đọc được qua REST.

```json
{
  "approval_id": "APR-20260816-0002",
  "session_id": "SESS-20260816-0007",
  "object_type": "IRRIGATION_SCHEDULE",
  "object_id": "PLAN-20260816-0001",
  "reason_vi": "Lượng nước 412 L vượt ngưỡng tự động 500 L? Không — vượt vì bồn dưới 30%.",
  "policy_rule": "APPROVAL_THRESHOLD_LITERS",
  "requested_at_iso": "2026-08-16T15:42:20+07:00",
  "status": "PENDING",
  "decided_at_iso": "",
  "decided_by": ""
}
```

`status`: `PENDING` · `APPROVED` · `REJECTED` · `EXPIRED`

---

## 4. HTTP API — FastAPI, cổng `8100`

Base: `http://localhost:8100`

### 4.1 Tạo phiên agent

```http
POST /api/v1/agent/sessions
Content-Type: application/json

{
  "user_request": "Hãy chuẩn bị kế hoạch tưới cho khu A trong hôm nay và giải thích dữ liệu đã sử dụng.",
  "requested_by": "manager_01"
}
```

`202 Accepted`:
```json
{
  "session_id": "SESS-20260816-0007",
  "stream_url": "/api/v1/agent/sessions/SESS-20260816-0007/stream",
  "created_at_iso": "2026-08-16T15:42:03+07:00"
}
```

Trả về **ngay lập tức**, không chờ agent chạy xong. Với model local một phiên có thể mất 15–40 giây — UI phải theo dõi qua stream.

### 4.2 Stream trace agent (SSE)

```http
GET /api/v1/agent/sessions/{session_id}/stream
Accept: text/event-stream
```

```
event: agent_event
data: {"event_id":"EVT-...","seq":1,"phase":"ROUTER","status":"STARTED",...}

event: agent_event
data: {"event_id":"EVT-...","seq":2,"phase":"ROUTER","status":"SUCCEEDED",...}

event: done
data: {"session_id":"SESS-20260816-0007","status":"COMPLETED"}
```

Payload của `event: agent_event` **chính là** `AgentEvent` ở §3.1 — cùng một hình dạng với message trên Kafka. Một schema, hai đường truyền.

### 4.3 Lấy kết quả đầy đủ

```http
GET /api/v1/agent/sessions/{session_id}
```

```json
{
  "session_id": "SESS-20260816-0007",
  "status": "COMPLETED",
  "user_request": "...",
  "playbook": "PLAN_IRRIGATION",
  "mode": "PARTIAL",
  "data_completeness": "5/6",
  "narrative": {
    "headline_vi": "Đề xuất tưới 412 L cho khu A lúc 16:30",
    "summary_vi": "...",
    "next_steps_vi": ["...", "..."]
  },
  "decisions": [
    {
      "decision_id": "DEC-1",
      "statement_vi": "Cần tưới khu A trong hôm nay.",
      "made_by_agent": "AgronomyAgent",
      "confidence": "CONFIDENT",
      "evidence_refs": ["EV-8821", "EV-8827"]
    }
  ],
  "evidence_ledger": [ /* EvidenceRecord[] — xem §3.2 */ ],
  "actions": [ /* IrrigationPlan / InspectionTicket / Notification */ ],
  "verification": { /* VerificationResult — xem §3.6 */ },
  "agent_events": [ /* AgentEvent[] — toàn bộ trace */ ],
  "timing": { "total_ms": 24180, "llm_calls": 6, "tool_calls": 11 }
}
```

`decisions[].evidence_refs` là thứ UI dùng để vẽ "quyết định này dựa trên dữ liệu nào" — nối sang `evidence_ledger` bằng `evidence_id`.

### 4.4 Phê duyệt (human-in-the-loop)

```http
POST /api/v1/approvals/{approval_id}
{ "decision": "APPROVED", "decided_by": "manager_01", "note_vi": "" }
```

`decision`: `APPROVED` · `REJECTED`

Trả `200` kèm `ApprovalRequest` đã cập nhật. Phiên agent đang treo sẽ tiếp tục và phát tiếp `AgentEvent`.

### 4.5 Các endpoint đọc

| Endpoint | Trả về |
|---|---|
| `GET /api/v1/plans?zone=&status=&limit=` | `IrrigationPlan[]` |
| `GET /api/v1/tasks?device_id=&status=&limit=` | `InspectionTicket[]` |
| `GET /api/v1/approvals?status=PENDING` | `ApprovalRequest[]` |
| `GET /api/v1/state/farm` | Farm State Snapshot hiện tại + độ mới từng thiết bị |
| `GET /api/v1/sessions?limit=` | Danh sách phiên gần đây (tóm tắt) |
| `GET /health` | `{status, llm_provider, llm_reachable, kafka_connected, devices_fresh}` |

**`GET /api/v1/state/farm`** — hữu ích cho frontend ngay cả khi chưa có agent:
```json
{
  "zone": "ZONE_A",
  "snapshot_at_iso": "2026-08-16T15:42:00+07:00",
  "data_completeness": "5/6",
  "mode": "PARTIAL",
  "devices": [
    {
      "device_id": "SOIL_01",
      "freshness": "FRESH",
      "age_seconds": 12,
      "last_seen_iso": "2026-08-16T15:41:59+07:00",
      "metrics": [
        {"metric": "soil_moisture", "value_text": "31.4", "unit": "%"},
        {"metric": "temperature", "value_text": "27.1", "unit": "°C"}
      ]
    }
  ]
}
```

**`GET /health`** nên được frontend poll để hiện chỉ báo "trạng thái kết nối và độ mới của dữ liệu" — yêu cầu UX bắt buộc của BTC.

---

## 5. Quy ước ID

| Tiền tố | Đối tượng | Mẫu |
|---|---|---|
| `SESS-` | Phiên agent | `SESS-20260816-0007` |
| `EVT-` | Agent event | `EVT-20260816-000123` |
| `EV-` | Evidence record | `EV-8821` |
| `PLAN-` | Lịch tưới | `PLAN-20260816-0001` |
| `TASK-` | Phiếu kiểm tra | `TASK-20260816-0007` |
| `NTF-` | Thông báo | `NTF-20260816-0011` |
| `VER-` | Kết quả xác minh | `VER-20260816-0003` |
| `APR-` | Yêu cầu phê duyệt | `APR-20260816-0002` |
| `DEC-` | Quyết định (trong phiên) | `DEC-1` |

Tiền tố khác nhau cho mọi loại là poka-yoke: một ID bị truyền nhầm chỗ sẽ lộ ra ngay, không âm thầm trỏ sai đối tượng.

---

## 6. Chỉ số đầu vào từ tầng stream

Để tránh nhầm khi các bên cùng đọc `topic_p`/`topic_h`: aggregator sinh key theo mẫu `{tên_field_gốc}_{avg|min|max|trend}`. Với 6 thiết bị Track B, key thực tế là:

| Thiết bị | Field trong payload MQTT | Key trong `metrics` của window |
|---|---|---|
| `SOIL_01` | `soil_moisture`, `temperature` | `soil_moisture_avg/min/max/trend`, `temperature_avg/...` |
| `WEATHER_01` | `temperature`, `humidity` | `temperature_avg/...`, `humidity_avg/...` |
| `PUMP_01` | `flow_rate`, `power` | `flow_rate_avg/...`, `power_avg/...` |
| `PH_01` | `ph` | `ph_avg/...` |
| `TANK_01` | `level` | `level_avg/...` |
| `SUN_01` | `lux` | `lux_avg/...` |

**Không có** key `temp_avg` — đây chính là nguồn gốc bug đang chặn pipeline, xem [04-integration-guide.md](04-integration-guide.md#việc-của-data--stream-engine).

Lưu ý thêm: mỗi window được gom **theo từng `device_id`**, nên một message trên `topic_p` chỉ chứa metric của **một** thiết bị. `PUMP_01.status` là string nên bị aggregator bỏ qua — muốn biết bơm ON/OFF phải đọc `topic_raw` hoặc suy từ `flow_rate_avg > 0`.
