# 02 — Đặc tả Agent & Tool Catalog (ACI)

> Skill `ai-agent-architecture-advisor` nhấn mạnh: **ACI (agent-computer interface) là điểm hay bị bỏ qua nhất** — phải đầu tư cho tài liệu và test tool kỹ như đầu tư cho giao diện người dùng. Tài liệu này là phần đó.

---

## Phần A — Quy ước chung

### A.1 Mọi lời gọi LLM đều tuân 5 quy tắc

1. **Một call = một việc.** Không có prompt nào vừa phân tích vừa quyết định vừa viết văn.
2. **Menu tool ≤ 4.** Quá 4 lựa chọn thì 3B bắt đầu chọn bừa.
3. **Đầu ra luôn là JSON schema ràng buộc** qua `response_format` (structured output), không parse text tự do.
4. **Prompt < ~2000 token.** Farm State đưa vào dưới dạng **bảng markdown**, không phải JSON — skill nêu rõ model quen markdown hơn JSON có escaping.
5. **Có stopping condition tường minh.** Không vòng lặp nào chạy vô hạn.

### A.2 Nguyên tắc thiết kế tool (poka-yoke)

Áp dụng "thiết kế sao cho khó dùng sai" vào bối cảnh cụ thể của mình:

| Nguyên tắc | Áp dụng ở đây |
|---|---|
| Tham số dùng `enum`, không free text | `device_id` là enum 6 giá trị, không phải string. LLM không thể gõ `"SOIL_1"` hay `"cảm biến đất"` |
| Thời gian tuyệt đối, không tương đối | Mọi field thời gian là ISO-8601 có offset (`2026-08-16T16:30:00+07:00`). **Cấm** `"chiều nay"`, `"trong 2 giờ nữa"` — 3B không có khái niệm "bây giờ" đáng tin |
| Đơn vị nằm trong tên field | `duration_minutes`, `volume_liters`, `level_pct` — không có field `duration` trần |
| Tool đọc không bao giờ trả `null` trần | Trả `{"status": "OFFLINE", "reason": "..."}`, để LLM buộc phải xử lý trường hợp thiếu dữ liệu thay vì lờ đi |
| Tool ghi luôn trả ID | Không có ID thì Verifier không đọc lại được → không có ID = không có verification |
| Tool ghi idempotent theo `idempotency_key` | Retry không tạo ra 2 lịch tưới trùng |
| Số liệu cảm biến **không** là tham số kiểu số | LLM truyền `evidence_refs`, code resolve ra số. Xem [ADR-003](adr/ADR-003-evidence-refs-only.md) |

### A.3 Hình dạng lỗi thống nhất

Mọi tool khi lỗi trả về **cùng một hình dạng**, để prompt không phải dạy LLM 12 kiểu lỗi khác nhau:

```json
{
  "ok": false,
  "error_code": "DEVICE_OFFLINE",
  "message": "SOIL_01 không có dữ liệu mới trong 743 giây.",
  "retryable": false,
  "suggested_action": "CREATE_INSPECTION_TICKET"
}
```

`error_code` là enum đóng: `DEVICE_OFFLINE` · `DEVICE_UNKNOWN` · `INSUFFICIENT_DATA` · `MODEL_COLD_START` · `POLICY_BLOCKED` · `APPROVAL_REQUIRED` · `NOT_FOUND` · `UPSTREAM_TIMEOUT` · `INVALID_ARGUMENT`.

---

## Phần B — Đặc tả từng Agent

### B.1 Router

| | |
|---|---|
| **Loại** | 1 lời gọi LLM, không tool |
| **Nhiệm vụ** | Phân loại yêu cầu người dùng thành playbook + trích slot |
| **Vào** | `user_request` (tiếng Việt), `now_iso` |
| **Ra** | `{playbook, zone, time_window_start, time_window_end, urgency, confidence}` |
| **Stopping** | 1 lần gọi. Parse lỗi → thử lại 1 lần → fallback heuristic từ khoá |
| **Nhiệt độ** | 0.1 |

**Playbook (enum đóng):**

| Playbook | Kích hoạt bởi | Worker được huy động |
|---|---|---|
| `PLAN_IRRIGATION` | "lập kế hoạch tưới", "hôm nay tưới thế nào" | IoT + Agronomy + Resource |
| `INSPECT_SESSION` | "kiểm tra phiên tưới hiện tại" | IoT + Resource |
| `DEVICE_ISSUE` | "cảm biến ngừng cập nhật", "bơm có vấn đề" | IoT + Resource |
| `REPORT` | "báo cáo tuần", "tổng hợp tình hình" | IoT + Agronomy |
| `ASK_DATA` | "độ ẩm đất khu A bao nhiêu" | IoT |

**Fallback tất định** khi LLM hỏng (bắt buộc có — model local có thể chết giữa demo): bảng từ khoá → playbook, mặc định `ASK_DATA` là an toàn nhất vì nó chỉ đọc, không hành động.

---

### B.2 Farm Coordinator (Orchestrator có chặn)

| | |
|---|---|
| **Loại** | LLM, tối đa 2 vòng dispatch |
| **Nhiệm vụ** | Quyết định hỏi worker nào, hỏi gì; tổng hợp findings; quyết định đã đủ dữ kiện chưa |
| **Vào** | `playbook`, `slots`, **Farm State Digest** (bảng markdown), findings vòng trước (nếu có) |
| **Ra** | `{dispatches: [{worker, question, device_scope}], reasoning, ready_to_act, data_completeness_ack}` |
| **Stopping** | `AGENT_MAX_DISPATCH_ROUNDS=2` (local) · dừng sớm khi `ready_to_act=true` · hết vòng mà chưa sẵn sàng → chuyển sang `PARTIAL` và đi tiếp, **không** lặp thêm |
| **Nhiệt độ** | 0.2 |

**Farm State Digest** — thứ Coordinator nhìn thấy. Cố tình nén để vừa context 3B:

```markdown
| Thiết bị | Chỉ số | Giá trị | Tuổi | Trạng thái | Evidence |
|---|---|---|---|---|---|
| SOIL_01 | soil_moisture | 31.4 % | 12s | FRESH | EV-8821 |
| SOIL_01 | temperature | 27.1 °C | 12s | FRESH | EV-8822 |
| WEATHER_01 | temperature | 33.8 °C | 9s | FRESH | EV-8823 |
| WEATHER_01 | humidity | 58.2 % | 9s | FRESH | EV-8824 |
| PUMP_01 | flow_rate | 0.0 L/min | 11s | FRESH | EV-8825 |
| PH_01 | ph | — | 812s | OFFLINE | — |
| TANK_01 | level | 78.5 % | 10s | FRESH | EV-8826 |
| SUN_01 | lux | 61200 lx | 10s | FRESH | EV-8827 |

data_completeness: 5/6 · chế độ: PARTIAL · thiết bị OFFLINE: PH_01
```

**Quy tắc cưỡng chế bằng code (không nằm trong prompt):** nếu `data_completeness < 1.0` mà Coordinator trả `ready_to_act=true` với `data_completeness_ack=false`, code **ép** đặt lại chế độ `PARTIAL` và bắt buộc Action Agent tạo phiếu kiểm tra cho thiết bị OFFLINE.

---

### B.3 Field IoT Agent

| | |
|---|---|
| **Nhiệm vụ** | Đọc & diễn giải trạng thái thiết bị; **gác cổng độ mới dữ liệu** |
| **Menu tool** | `get_device_snapshot` · `get_metric_series` · `get_freshness_report` · `get_anomaly_report` |
| **Ra** | `{findings: [{claim, evidence_refs, confidence}], offline_devices, stale_devices, data_completeness}` |
| **Stopping** | Tối đa 3 lần gọi tool trong một lượt |

Đây là agent **duy nhất** được phép chạm vào dữ liệu cảm biến thô. Mọi agent khác phải nhận số liệu qua `evidence_refs` mà agent này phát ra. Tập trung quyền đọc vào một chỗ là điều làm cho Evidence Ledger có hiệu lực.

---

### B.4 Agronomy Agent

| | |
|---|---|
| **Nhiệm vụ** | Phán đoán nông học: có cần tưới không, khi nào, ưu tiên ra sao, đánh đổi gì |
| **Menu tool** | `estimate_water_demand` · `forecast_soil_moisture` · `get_crop_profile` |
| **Ra** | `{need_irrigation, rationale, preferred_window_start, preferred_window_end, priority, tradeoffs, evidence_refs}` |
| **Stopping** | Tối đa 3 lần gọi tool |
| **Nhiệt độ** | 0.2 |

**Ranh giới quan trọng:** agent này **không tính lượng nước**. Nó gọi `estimate_water_demand` (code + ML tính) rồi *diễn giải* kết quả — cân nhắc thời điểm nắng gắt, dự báo độ ẩm, ưu tiên giữa các khu. Con số đến từ [05-ml-interfaces.md](05-ml-interfaces.md), không từ LLM.

Đây chính là chỗ tách biệt `agent-core` khỏi code rule-based hiện tại: `irrigation_planning_agent.py` trên `main` tính `deficit * 15.0`; ở đây con số đến từ mô hình ET0 + dự báo độ ẩm, còn LLM lo phần phán đoán mà công thức không biểu diễn được.

---

### B.5 Resource Agent

| | |
|---|---|
| **Nhiệm vụ** | Kiểm tra tính khả thi: đủ nước không, bơm có khoẻ không, ai làm được việc |
| **Menu tool** | `get_water_balance` · `get_pump_health` · `get_staff_roster` · `get_open_tasks` |
| **Ra** | `{feasible, blocking_constraints, warnings, suggested_assignee, evidence_refs}` |
| **Stopping** | Tối đa 3 lần gọi tool |

**Lưu ý:** agent này *báo cáo* ràng buộc, nó **không** phải là cổng an toàn. Cổng an toàn thật là Policy Gate bằng code (§B.7) — vì không được để một model 3B đứng giữa lệnh bơm nước và thực tế vật lý.

---

### B.6 Farm Action Agent

| | |
|---|---|
| **Nhiệm vụ** | Chuyển kế hoạch đã tổng hợp thành **một** hành động có cấu trúc |
| **Menu tool** | `create_irrigation_schedule` · `create_inspection_ticket` · `send_notification` · `generate_report` |
| **Ra** | Đúng **1** action object hợp lệ theo schema |
| **Stopping** | 1 hành động / 1 lượt. Cần nhiều hành động → Coordinator gọi lại nhiều lượt |

LLM ở bước này **chỉ điền schema**. Nó không gọi tool trực tiếp — output của nó đi vào Policy Gate trước.

---

### B.7 Policy Gate — **code, không phải LLM**

Chặn giữa "LLM muốn làm gì" và "hệ thống thực sự làm gì". Ràng buộc cứng, kiểm bằng code, không thể bị prompt injection hay ảo giác vượt qua:

| Luật | Ngưỡng | Vi phạm thì |
|---|---|---|
| Mực bồn tối thiểu | `TANK_01.level >= POLICY_MIN_TANK_LEVEL_PCT` (20%) | `POLICY_BLOCKED` — chuyển sang tạo cảnh báo cấp nước |
| Ngưỡng cần người duyệt | `volume_liters > POLICY_APPROVAL_THRESHOLD_LITERS` (500) | `APPROVAL_REQUIRED` — treo chờ `POST /api/v1/approvals/{id}` |
| Bơm phải khoẻ | `pump_health != FAULT` | `POLICY_BLOCKED` — chuyển sang tạo phiếu bảo trì |
| Evidence phải tươi | Mọi `evidence_refs` của quyết định `confident` phải là `FRESH` | `POLICY_BLOCKED` — hạ cấp xuống `tentative` |
| Chặn trên tuyệt đối | `volume_liters <= 2000` và `duration_minutes <= 120` | `INVALID_ARGUMENT` — cắt về ngưỡng và ghi cảnh báo |

> Điểm phản biện trước giám khảo: *"AI của các bạn có thể ra lệnh bơm sai không?"* → Có thể **đề xuất** sai, nhưng không thể **thực thi** sai: mọi hành động đi qua cổng tất định này, và mọi hành động vượt ngưỡng đều dừng lại chờ người duyệt.

---

### B.8 Verifier — **code + 1 lời gọi LLM tuỳ chọn**

Đây là phần code hiện tại làm giả (`"verified": True` hardcode). Ở đây nó là thật:

```
1. read_back(id)              → đọc lại đối tượng vừa tạo từ store
2. diff_against_intent(...)   → so từng field với ý định ban đầu
3. audit_evidence(...)        → mọi quyết định có ≥1 evidence_ref?
                                evidence có tươi không?
                                có số nào không truy được về evidence không?
4. → VERIFIED | MISMATCH | PARTIAL
```

| Kết quả | Nghĩa | Xử lý |
|---|---|---|
| `VERIFIED` | Đọc lại khớp hoàn toàn, evidence hợp lệ | Đi tiếp sang viết bản tin |
| `PARTIAL` | Tạo thành công nhưng có quyết định dựa trên dữ liệu STALE | Đi tiếp, **ghi rõ giới hạn dữ liệu trong bản tin** |
| `MISMATCH` | Đọc lại lệch, hoặc có quyết định trích dẫn thiết bị OFFLINE | **1 lần** retry Action Agent kèm diff làm feedback → vẫn lệch thì escalate cho người |

Vòng retry tối đa **1 lần** (`Evaluator-optimizer` có chặn) — 3B không cải thiện đáng kể sau lần thứ hai, chỉ tốn thời gian demo.

---

### B.9 Narrative Agent

| | |
|---|---|
| **Nhiệm vụ** | Viết bản tin tiếng Việt cho người quản lý đọc trên điện thoại |
| **Vào** | Kế hoạch đã xác minh + evidence ledger **đã resolve sẵn thành text** |
| **Ra** | `{headline, summary_vi, next_steps_vi}` |
| **Nhiệt độ** | 0.6 |

**Cấm tuyệt đối:** agent này không nhận `evidence_id` chưa resolve và không được phát ra con số nào không có trong input. Code chạy một bước kiểm sau cùng: mọi token dạng số trong output phải xuất hiện trong input. Lệch → bỏ, dùng template tất định thay thế.

---

## Phần C — Tool Catalog

> Format: mỗi tool có **mô tả · tham số · trả về · lỗi · ví dụ · ghi chú poka-yoke**. Đây là mức chi tiết mà skill yêu cầu ("như viết docstring cho một dev mới vào team").

### C.1 Enum dùng chung

```
DeviceId    = SOIL_01 | WEATHER_01 | PUMP_01 | PH_01 | TANK_01 | SUN_01
Metric      = soil_moisture | temperature | humidity | flow_rate | power | ph | level | lux
Freshness   = FRESH | STALE | OFFLINE
Zone        = ZONE_A
WindowType  = TUMBLING_1M | SLIDING_10M | HOURLY_1H
Priority    = LOW | MEDIUM | HIGH | CRITICAL
```

> `Zone` hiện chỉ có `ZONE_A` vì đề bài Track B chỉ mô tả khu A. Giữ là enum để mở rộng không phải đổi schema.

---

### C.2 Tool đọc — Field IoT Agent

#### `get_device_snapshot`

**Mô tả cho LLM:** Đọc giá trị mới nhất của các thiết bị đã chỉ định, kèm tuổi dữ liệu và trạng thái độ mới. Dùng tool này trước tiên trong hầu hết mọi tác vụ. Trả về bảng markdown, mỗi giá trị có một `evidence_id` — hãy dùng `evidence_id` đó khi cần nhắc tới số liệu này về sau.

| Tham số | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `device_ids` | `DeviceId[]` | ✅ | Enum. Mảng rỗng = lấy cả 6 thiết bị |

**Trả về:** bảng markdown (`device_id`, `metric`, `value`, `unit`, `age_seconds`, `freshness`, `evidence_id`) + dòng tổng kết `data_completeness`.

**Lỗi:** `DEVICE_UNKNOWN` (id ngoài enum) · `UPSTREAM_TIMEOUT` (Farm State Store không phản hồi).

**Không bao giờ** trả `null` cho thiết bị chết — trả dòng có `freshness: OFFLINE`, `value: "—"`, không có `evidence_id`. Buộc LLM phải nhìn thấy sự vắng mặt thay vì lướt qua nó.

**Ví dụ:**
```json
{"device_ids": ["SOIL_01", "TANK_01"]}
```
```markdown
| device_id | metric | value | unit | age_seconds | freshness | evidence_id |
|---|---|---|---|---|---|---|
| SOIL_01 | soil_moisture | 31.4 | % | 12 | FRESH | EV-8821 |
| SOIL_01 | temperature | 27.1 | °C | 12 | FRESH | EV-8822 |
| TANK_01 | level | 78.5 | % | 10 | FRESH | EV-8826 |

data_completeness: 2/2 thiết bị được yêu cầu đang FRESH
```

---

#### `get_metric_series`

**Mô tả cho LLM:** Lấy chuỗi thời gian đã gom cửa sổ của một chỉ số, để nhìn xu hướng thay vì một điểm. Dùng khi cần biết chỉ số đang tăng hay giảm.

| Tham số | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `device_id` | `DeviceId` | ✅ | |
| `metric` | `Metric` | ✅ | Phải là chỉ số thiết bị đó thực sự phát ra |
| `lookback_minutes` | `int` 5–1440 | ✅ | Ngoài khoảng → `INVALID_ARGUMENT` |
| `window_type` | `WindowType` | ❌ | Mặc định `TUMBLING_1M`; > 360 phút tự nâng lên `HOURLY_1H` |

**Trả về:** tối đa **24 điểm** đã lấy mẫu xuống (giữ prompt nhỏ), kèm `first`, `last`, `min`, `max`, `trend_per_hour`, và **một** `evidence_id` cho cả chuỗi.

**Lỗi:** `INSUFFICIENT_DATA` (< 3 điểm) · `DEVICE_OFFLINE` · `INVALID_ARGUMENT`.

Luôn giới hạn 24 điểm bất kể `lookback_minutes` — chuỗi 1440 điểm sẽ làm nổ context 3B.

---

#### `get_freshness_report`

**Mô tả cho LLM:** Kiểm tra thiết bị nào đang gửi dữ liệu và thiết bị nào đã ngừng. Dùng tool này khi người dùng nhắc tới sự cố cảm biến, hoặc khi bạn định kết luận điều gì đó mà cần chắc dữ liệu còn mới.

Không tham số.

**Trả về:** `{fresh: [...], stale: [{device_id, age_seconds}], offline: [{device_id, age_seconds, last_seen_iso}], data_completeness: "5/6", mode: "PARTIAL"}`

Đây là tool rẻ nhất và nên gọi đầu tiên ở playbook `DEVICE_ISSUE`.

---

#### `get_anomaly_report`

**Mô tả cho LLM:** Hỏi lớp mô hình phát hiện bất thường xem có gì lạ trong khoảng thời gian gần đây không. Trả về bất thường đã phát hiện kèm điểm số, **không** kèm khuyến nghị — việc diễn giải là của bạn.

| Tham số | Kiểu | Bắt buộc |
|---|---|---|
| `zone` | `Zone` | ✅ |
| `lookback_minutes` | `int` 10–720 | ❌ (mặc định 60) |

**Trả về:** `[{anomaly_type, device_id, score_0_1, detected_at_iso, model_version, evidence_refs}]`

**Lỗi:** `MODEL_COLD_START` — mô hình chưa đủ dữ liệu lịch sử. Đây là lỗi **bình thường** trong 10 phút đầu chạy hệ thống; LLM phải coi là "chưa biết", không phải "không có bất thường".

---

### C.3 Tool định lượng — Agronomy Agent

> Ba tool này là nơi phần "AI thật" nằm. Chi tiết mô hình: [05-ml-interfaces.md](05-ml-interfaces.md).

#### `estimate_water_demand`

**Mô tả cho LLM:** Tính lượng nước cần cho một khu, dựa trên mô hình bốc-thoát hơi nước (ET0) và độ thiếu ẩm hiện tại. **Đây là nguồn con số duy nhất được chấp nhận cho lượng nước** — không được tự tính.

| Tham số | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `zone` | `Zone` | ✅ | |
| `target_moisture_pct` | `float` 30–80 | ❌ | Mặc định lấy từ crop profile |
| `horizon_hours` | `int` 1–24 | ❌ | Mặc định 6 |

**Trả về:**
```json
{
  "ok": true,
  "volume_liters": 412.0,
  "confidence_low": 355.0,
  "confidence_high": 470.0,
  "et0_mm_day": 5.8,
  "method": "hargreaves+moisture_deficit",
  "model_version": "wd-baseline-0.1",
  "evidence_refs": ["EV-8821", "EV-8823", "EV-8827"]
}
```

**Lỗi:** `INSUFFICIENT_DATA` (SOIL_01 hoặc WEATHER_01 không FRESH) · `MODEL_COLD_START`.

Luôn trả kèm khoảng tin cậy. Một con số trần khuyến khích LLM tin tuyệt đối; một khoảng buộc nó diễn đạt độ không chắc chắn — điều BTC chấm ở mục *"tránh kết luận quá mức khi thiếu dữ liệu"*.

---

#### `forecast_soil_moisture`

**Mô tả cho LLM:** Dự báo độ ẩm đất tại các mốc tương lai nếu **không** tưới. Dùng để quyết định tưới ngay hay hoãn tới chiều mát.

| Tham số | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `device_id` | `DeviceId` | ✅ | Thực tế là `SOIL_01` |
| `horizons_minutes` | `int[]` | ❌ | Mặc định `[30, 60, 120, 360]`; tối đa 6 mốc |

**Trả về:** `[{horizon_minutes, predicted_pct, ci_low, ci_high}]` + `model_version` + `evidence_refs`.

**Lỗi:** `MODEL_COLD_START` (chưa đủ lịch sử → rơi về mô hình suy giảm vật lý, `model_version: "physics-fallback"`) · `DEVICE_OFFLINE`.

---

#### `get_crop_profile`

**Mô tả cho LLM:** Lấy ngưỡng nông học của cây trồng đang canh tác ở khu này (khoảng ẩm tối ưu, khoảng pH, độ nhạy nắng).

| Tham số | Kiểu | Bắt buộc |
|---|---|---|
| `zone` | `Zone` | ✅ |

**Trả về:** `{crop_name, moisture_optimal_min_pct, moisture_optimal_max_pct, moisture_critical_pct, ph_optimal_min, ph_optimal_max, area_m2, notes_vi}`

Dữ liệu cấu hình tĩnh (`config/crop_profiles.yaml`) — không phải mô hình. Nó cho LLM *ngữ cảnh* để diễn giải, không phải quyết định thay.

---

### C.4 Tool tài nguyên — Resource Agent

#### `get_water_balance`

**Mô tả cho LLM:** Kiểm tra thực tế còn bao nhiêu nước dùng được và bơm được bao lâu.

| Tham số | Kiểu | Bắt buộc |
|---|---|---|
| `zone` | `Zone` | ✅ |

**Trả về:** `{tank_level_pct, usable_liters, tank_capacity_liters, current_flow_rate_lpm, estimated_runtime_minutes, below_safety_threshold, evidence_refs}`

`usable_liters` đã **trừ** phần dự trữ an toàn dưới `POLICY_MIN_TANK_LEVEL_PCT` — nên LLM không thể vô tình lập kế hoạch dùng tới đáy bồn. Poka-yoke ở tầng dữ liệu trả về.

---

#### `get_pump_health`

**Mô tả cho LLM:** Hỏi mô hình chẩn đoán tình trạng bơm. Bơm có thể đang chạy mà vẫn hỏng (tắc lọc, chạy khô).

| Tham số | Kiểu | Bắt buộc |
|---|---|---|
| `device_id` | `DeviceId` | ✅ (`PUMP_01`) |

**Trả về:** `{status: OK|DEGRADED|FAULT|UNKNOWN, efficiency_lpm_per_watt, baseline_efficiency, deviation_pct, symptom, model_version, evidence_refs}`

`symptom` là enum: `NONE` · `LOW_FLOW_NORMAL_POWER` (nghi tắc lọc) · `HIGH_POWER_NO_FLOW` (nghi chạy khô) · `INTERMITTENT`.

Tính trên **tỉ số** `flow_rate / power` chứ không phải ngưỡng tuyệt đối trên từng chỉ số — đây là điểm khiến nó là chẩn đoán, không phải cảnh báo rule-based.

---

#### `get_staff_roster`

**Mô tả cho LLM:** Xem ai đang có ca và làm được loại việc gì, để giao nhiệm vụ hiện trường cho đúng người.

| Tham số | Kiểu | Bắt buộc |
|---|---|---|
| `date_iso` | `string` (YYYY-MM-DD) | ✅ |
| `skill` | `enum` `IRRIGATION\|SENSOR_REPAIR\|PUMP_MAINTENANCE\|GENERAL` | ❌ |

**Trả về:** `[{staff_id, name, shift_start_iso, shift_end_iso, skills, current_task_count}]`

Nguồn: dữ liệu mô phỏng (`config/staff_roster.yaml`) — đề bài cho phép *"nhân sự hoặc tài nguyên mô phỏng"*.

---

#### `get_open_tasks`

**Mô tả cho LLM:** Liệt kê nhiệm vụ đang mở, để không tạo phiếu trùng cho cùng một sự cố.

| Tham số | Kiểu | Bắt buộc |
|---|---|---|
| `zone` | `Zone` | ❌ |
| `device_id` | `DeviceId` | ❌ |

**Trả về:** `[{task_id, device_id, issue_type, priority, status, created_at_iso, assignee}]`

Gọi tool này **trước** `create_inspection_ticket` là bắt buộc trong playbook `DEVICE_ISSUE` — chống spam phiếu khi một cảm biến chết suốt 20 phút.

---

### C.5 Tool ghi — Farm Action Agent

> Mọi tool ghi: **idempotent theo `idempotency_key`** · **trả về ID** · **đi qua Policy Gate trước khi thực thi**.

#### `create_irrigation_schedule`

**Mô tả cho LLM:** Tạo một lịch tưới trong hệ thống. Hành động này có hệ quả thật — chỉ gọi khi Resource Agent xác nhận khả thi. Nếu lượng nước vượt ngưỡng, lịch sẽ được tạo ở trạng thái chờ người quản lý phê duyệt.

| Tham số | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `zone` | `Zone` | ✅ | |
| `start_time_iso` | `string` ISO-8601 **có offset** | ✅ | `2026-08-16T16:30:00+07:00`. **Cấm** thời gian tương đối |
| `duration_minutes` | `int` 1–120 | ✅ | |
| `target_volume_liters` | `float` 1–2000 | ✅ | **Phải** lấy từ `estimate_water_demand` |
| `priority` | `Priority` | ✅ | |
| `reason_vi` | `string` ≤ 300 ký tự | ✅ | Vì sao tưới — người đọc |
| `evidence_refs` | `string[]` | ✅ | **≥1**. Rỗng → `INVALID_ARGUMENT` |
| `idempotency_key` | `string` | ✅ | Gợi ý: `{zone}-{start_time_iso}` |

**Trả về:** `{ok: true, schedule_id: "PLAN-20260816-0001", status: "SCHEDULED"|"PENDING_APPROVAL", created_at_iso}`

**Lỗi:** `POLICY_BLOCKED` (bồn dưới ngưỡng / bơm FAULT) · `APPROVAL_REQUIRED` (vượt ngưỡng — kèm `approval_id`) · `INVALID_ARGUMENT` (thiếu evidence, thời gian tương đối, quá chặn trên).

`evidence_refs` bắt buộc ≥1 là ràng buộc quan trọng nhất: **không thể tạo lịch tưới mà không nêu căn cứ dữ liệu.**

---

#### `create_inspection_ticket`

**Mô tả cho LLM:** Tạo phiếu kiểm tra hiện trường cho thiết bị nghi có vấn đề. Gọi `get_open_tasks` trước để không tạo trùng.

| Tham số | Kiểu | Bắt buộc | Ghi chú |
|---|---|---|---|
| `device_id` | `DeviceId` | ✅ | |
| `issue_type` | `enum` `SENSOR_OFFLINE\|SENSOR_DRIFT\|PUMP_FAULT\|LOW_TANK\|PH_OUT_OF_RANGE\|OTHER` | ✅ | |
| `priority` | `Priority` | ✅ | |
| `description_vi` | `string` ≤ 500 | ✅ | Việc cần làm, cụ thể |
| `assignee_staff_id` | `string` | ❌ | Từ `get_staff_roster` |
| `evidence_refs` | `string[]` | ✅ | **≥1** |
| `idempotency_key` | `string` | ✅ | Gợi ý: `{device_id}-{issue_type}-{yyyymmddHH}` |

**Trả về:** `{ok: true, ticket_id: "TASK-20260816-0007", status: "OPEN", created_at_iso}`

**Lỗi:** `INVALID_ARGUMENT` · `NOT_FOUND` (assignee không có trong roster).

Với `issue_type: SENSOR_OFFLINE`, `evidence_refs` có thể trỏ tới **bản ghi vắng mặt** (`get_freshness_report` cũng phát evidence_id) — sự vắng mặt của dữ liệu cũng là bằng chứng.

---

#### `send_notification`

**Mô tả cho LLM:** Gửi thông báo tới người quản lý hoặc đội hiện trường.

| Tham số | Kiểu | Bắt buộc |
|---|---|---|
| `audience` | `enum` `MANAGER\|FIELD_TEAM\|AGRONOMIST` | ✅ |
| `severity` | `enum` `INFO\|WARNING\|CRITICAL` | ✅ |
| `title_vi` | `string` ≤ 80 | ✅ |
| `body_vi` | `string` ≤ 500 | ✅ |
| `evidence_refs` | `string[]` | ✅ (≥1 khi `severity != INFO`) |
| `idempotency_key` | `string` | ✅ |

**Trả về:** `{ok: true, notification_id, delivered_at_iso}`

Kênh gửi thật là Kafka `topic_notifications` → WebSocket → UI. Không gửi SMS/email thật trong phạm vi cuộc thi.

---

#### `generate_report`

**Mô tả cho LLM:** Sinh báo cáo canh tác cho một khoảng thời gian.

| Tham số | Kiểu | Bắt buộc |
|---|---|---|
| `zone` | `Zone` | ✅ |
| `period_start_iso` / `period_end_iso` | `string` ISO-8601 | ✅ |
| `sections` | `enum[]` `MOISTURE_TREND\|IRRIGATION_HISTORY\|ANOMALIES\|RESOURCE_USAGE\|OPEN_TASKS` | ✅ |

**Trả về:** `{ok: true, report_id, section_count, evidence_count}`

Nội dung báo cáo do **code** tổng hợp từ store; LLM chỉ chọn section và viết phần dẫn nhập. Bảng số liệu trong báo cáo không đi qua LLM.

---

### C.6 Tool xác minh — Verifier

#### `read_back`

**Mô tả:** Đọc lại đối tượng vừa tạo, **từ store chứ không từ bộ nhớ phiên làm việc**.

| Tham số | Kiểu | Bắt buộc |
|---|---|---|
| `object_type` | `enum` `IRRIGATION_SCHEDULE\|INSPECTION_TICKET\|NOTIFICATION\|REPORT` | ✅ |
| `object_id` | `string` | ✅ |

**Trả về:** đối tượng đầy đủ, hoặc `{ok: false, error_code: "NOT_FOUND"}`.

Bắt buộc đọc từ store. Đọc từ biến trong RAM chính là cách code hiện tại tạo ra verification giả.

---

#### `diff_against_intent`

**Mô tả:** So sánh đối tượng đọc lại với ý định ban đầu, từng field.

**Trả về:** `{match: bool, differences: [{field, intended, actual}]}`

---

#### `audit_evidence`

**Mô tả:** Kiểm tra chuỗi bằng chứng của một phiên làm việc.

**Trả về:**
```json
{
  "ok": true,
  "decisions_total": 4,
  "decisions_without_evidence": 0,
  "stale_evidence_used": ["EV-8801"],
  "offline_evidence_used": [],
  "unsourced_numbers": [],
  "verdict": "PARTIAL"
}
```

`unsourced_numbers` là mẻ lưới cuối: quét output tìm token số không truy được về evidence nào. Khác rỗng → `MISMATCH`.

---

## Phần D — Bảng tóm tắt tool

| Tool | Agent | Ghi? | Bắt buộc evidence | Qua Policy Gate |
|---|---|---|---|---|
| `get_device_snapshot` | Field IoT | ❌ | — | ❌ |
| `get_metric_series` | Field IoT | ❌ | — | ❌ |
| `get_freshness_report` | Field IoT | ❌ | — | ❌ |
| `get_anomaly_report` | Field IoT | ❌ | — | ❌ |
| `estimate_water_demand` | Agronomy | ❌ | — | ❌ |
| `forecast_soil_moisture` | Agronomy | ❌ | — | ❌ |
| `get_crop_profile` | Agronomy | ❌ | — | ❌ |
| `get_water_balance` | Resource | ❌ | — | ❌ |
| `get_pump_health` | Resource | ❌ | — | ❌ |
| `get_staff_roster` | Resource | ❌ | — | ❌ |
| `get_open_tasks` | Resource | ❌ | — | ❌ |
| `create_irrigation_schedule` | Action | ✅ | ✅ ≥1 | ✅ |
| `create_inspection_ticket` | Action | ✅ | ✅ ≥1 | ✅ |
| `send_notification` | Action | ✅ | ✅ nếu ≠INFO | ✅ |
| `generate_report` | Action | ✅ | ❌ | ✅ |
| `read_back` | Verifier | ❌ | — | ❌ |
| `diff_against_intent` | Verifier | ❌ | — | ❌ |
| `audit_evidence` | Verifier | ❌ | — | ❌ |

**18 tool, nhưng không agent nào thấy quá 4 cùng lúc** — đây là điều làm cho model 3B dùng được chúng.
