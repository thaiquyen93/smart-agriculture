# 06 — Kịch bản BTC & Checklist nghiệm thu

> Dùng file này để: (a) biết chính xác hệ thống phải làm gì trong 3 kịch bản BTC ra đề, (b) tự chấm trước khi nộp, (c) chuẩn bị phản biện.

---

## Kịch bản 1 — Lập kế hoạch tưới trong ngày

> *"Hãy chuẩn bị kế hoạch tưới cho khu A trong hôm nay và giải thích dữ liệu đã sử dụng."*
> BTC chấm: **cách phối hợp Agent, sử dụng dữ liệu và giá trị của kế hoạch** — không chấm một công thức tưới duy nhất.

### Trace kỳ vọng

| # | Phase | Agent | Hành động | LLM? |
|---|---|---|---|---|
| 1 | `ROUTER` | Router | → `playbook=PLAN_IRRIGATION`, `zone=ZONE_A` | ✅ |
| 2 | `COORDINATOR` | Coordinator | Đọc Farm State Digest (6/6 FRESH) → dispatch 3 worker kèm câu hỏi cụ thể | ✅ |
| 3 | `WORKER` | Field IoT | `get_device_snapshot([tất cả])`, `get_metric_series(SOIL_01, soil_moisture, 120)` → phát `EV-88xx` | ✅ |
| 4 | `WORKER` | Agronomy | `get_crop_profile`, `estimate_water_demand`, `forecast_soil_moisture` → *"cần tưới; hoãn tới 16:30 vì lux đang đỉnh, dự báo ẩm còn 28% lúc đó — vẫn an toàn"* | ✅ |
| 5 | `WORKER` | Resource | `get_water_balance`, `get_pump_health`, `get_staff_roster` → *"đủ nước, bơm OK"* | ✅ |
| 6 | `COORDINATOR` | Coordinator | Tổng hợp → `ready_to_act=true` | ✅ |
| 7 | `ACTION` | Farm Action | Điền schema `create_irrigation_schedule` | ✅ |
| 8 | `POLICY_GATE` | *(code)* | Bồn 78% > 20% ✅ · 412L < 500L → **không cần duyệt** | ❌ |
| 9 | `TOOL` | *(code)* | Thực thi → `PLAN-20260816-0001` | ❌ |
| 10 | `VERIFY` | Verifier | `read_back` → 8/8 field khớp · `audit_evidence` → 4/4 quyết định có evidence FRESH → `VERIFIED` | ❌ |
| 11 | `NARRATIVE` | Narrative | Bản tin tiếng Việt | ✅ |

**6 agent phối hợp** (vượt xa yêu cầu ≥2) · **6 LLM call** · ~25 giây trên model local.

### Đầu ra kỳ vọng

Bản tin nêu được: tưới bao nhiêu, khi nào, **vì sao** (dẫn số liệu cụ thể kèm thời điểm đo), và **đánh đổi đã cân nhắc** (vì sao 16:30 chứ không phải ngay bây giờ). Kèm bảng evidence 4–8 dòng.

### Điểm dễ mất

- Bản tin nói "độ ẩm thấp nên tưới" mà không có con số → thiếu *"giải thích dữ liệu đã sử dụng"*
- Không thể hiện đánh đổi → kế hoạch trông như đầu ra công thức, mất phần *"giá trị của kế hoạch"*
- Trace không hiện agent nào làm gì → mất phần *"cách phối hợp Agent"*

---

## Kịch bản 2 — Kiểm tra hoạt động tưới

> *"Hãy kiểm tra phiên tưới hiện tại và chuẩn bị công việc cần thực hiện nếu kết quả không như mong đợi."*
> BTC chấm: **dữ liệu MQTT có được dùng để chọn nội dung công việc không · hệ thống có tránh kết luận quá mức khi thiếu dữ liệu không.**

### Tình huống dựng để demo
`PUMP_01` chạy (`flow_rate ≈ 12 L/min`, `power ≈ 750W`) nhưng `SOIL_01.soil_moisture` **không tăng** sau 10 phút.

### Trace kỳ vọng

| # | Phase | Agent | Hành động |
|---|---|---|---|
| 1 | `ROUTER` | Router | → `playbook=INSPECT_SESSION` |
| 2 | `COORDINATOR` | Coordinator | Dispatch Field IoT + Resource |
| 3 | `WORKER` | Field IoT | `get_metric_series(PUMP_01, flow_rate, 30)` + `(SOIL_01, soil_moisture, 30)` → *"bơm có lưu lượng, ẩm đất đi ngang"* |
| 4 | `WORKER` | Field IoT | `get_anomaly_report` → `cross_device_consistency`: bơm chạy mà đất không ẩm lên, score 0.87 |
| 5 | `WORKER` | Resource | `get_pump_health` → `DEGRADED`, hiệu suất lệch −22% so với nền, `symptom=LOW_FLOW_NORMAL_POWER` |
| 6 | `COORDINATOR` | Coordinator | **Ba giả thuyết:** vỡ ống · tắc đầu tưới · `SOIL_01` hỏng. Dữ liệu hiện có **không phân biệt được** → cần người ra hiện trường |
| 7 | `ACTION` | Farm Action | `get_open_tasks` (chống trùng) → `create_inspection_ticket(PUMP_01, PUMP_FAULT, HIGH, ...)` |
| 8 | `TOOL` + `VERIFY` | *(code)* | Tạo `TASK-...` → `read_back` xác nhận tồn tại → `VERIFIED` |
| 9 | `NARRATIVE` | Narrative | Nêu triệu chứng, 3 giả thuyết, việc cần làm |

### Điểm mấu chốt — bước 6

Hệ thống **liệt kê giả thuyết chưa phân định được** thay vì chọn bừa một nguyên nhân. Đây chính xác là thứ BTC gọi là *"tránh kết luận quá mức"*. Nội dung phiếu kiểm tra phải yêu cầu kiểm **cả ba** khả năng, và phải trích dẫn evidence cụ thể (chuỗi lưu lượng bơm + chuỗi ẩm đất) làm căn cứ — đó là *"dữ liệu MQTT được dùng để chọn nội dung công việc"*.

---

## Kịch bản 3 — Dữ liệu hiện trường bị gián đoạn

> *"Dữ liệu một số cảm biến vừa ngừng cập nhật. Hãy tiếp tục lập kế hoạch công việc cho đội ngoài hiện trường."*
> BTC chấm: **Không bịa giá trị mới · Có khả năng tiếp tục tác vụ ở chế độ partial · Có hành động kiểm tra phù hợp.**

### Tình huống dựng để demo
Dừng phát `PH_01` và `SUN_01`. Sau 10 phút cả hai chuyển `OFFLINE`. Gửi yêu cầu lập kế hoạch.

### Trace kỳ vọng

| # | Phase | Agent | Hành động |
|---|---|---|---|
| 1 | `ROUTER` | Router | → `PLAN_IRRIGATION` |
| 2 | `COORDINATOR` | Coordinator | Digest hiện `data_completeness: 4/6`, `mode: PARTIAL` |
| 3 | `WORKER` | Field IoT | `get_freshness_report` → `offline: [PH_01 (734s), SUN_01 (698s)]`. Phát **evidence vắng mặt** `is_absence_record=true` |
| 4 | `WORKER` | Agronomy | `estimate_water_demand` → thiếu `SUN_01` nên ET0 kém chính xác → khoảng tin cậy **rộng hơn** (300–520 L thay vì 355–470 L) |
| 5 | `COORDINATOR` | Coordinator | **Tách hai nhóm:**<br/>`confident_actions`: tưới theo ẩm đất (SOIL_01, WEATHER_01, TANK_01 đều FRESH)<br/>`needs_verification`: điều chỉnh pH (không có dữ liệu PH_01) |
| 6 | `ACTION` | Farm Action | 3 hành động: lịch tưới (`confidence=TENTATIVE`) + 2 phiếu kiểm tra `SENSOR_OFFLINE` cho PH_01 và SUN_01 |
| 7 | `POLICY_GATE` | *(code)* | Evidence còn tươi cho phần tưới ✅ · pH không có evidence → **chặn** mọi quyết định liên quan pH |
| 8 | `VERIFY` | Verifier | `audit_evidence` → không có quyết định `confident` nào trích dẫn thiết bị OFFLINE → `PARTIAL` |
| 9 | `NARRATIVE` | Narrative | **Ghi rõ giới hạn dữ liệu ngay trong bản tin** |

### Ba điều BTC quan sát — cơ chế tương ứng

| BTC quan sát | Cơ chế bảo đảm | Cưỡng chế ở đâu |
|---|---|---|
| Không bịa giá trị mới | Schema đầu ra của LLM không có field số cho giá trị cảm biến; chỉ có `evidence_refs`. Thiết bị OFFLINE không phát evidence → không có gì để tham chiếu | **Code** ([ADR-003](adr/ADR-003-evidence-refs-only.md)) |
| Tiếp tục ở chế độ partial | `mode=PARTIAL` + tách `confident_actions` / `needs_verification`; hệ thống vẫn ra kế hoạch cho phần dữ liệu còn tốt | **Code** ép khi `data_completeness < 1.0` |
| Hành động kiểm tra phù hợp | Bắt buộc tạo `create_inspection_ticket(issue_type=SENSOR_OFFLINE)` cho mọi thiết bị OFFLINE | **Code** ép ở Policy Gate |

Cả ba đều là ràng buộc tất định, không phải hướng dẫn trong prompt. Với model 3B, đây là khác biệt giữa "thường đúng" và "luôn đúng".

---

## Checklist nghiệm thu — "Điều kiện chấp nhận theo Track"

| # | Điều kiện BTC | Đáp ứng bởi | Kiểm bằng cách nào | ✓ |
|---|---|---|---|---|
| 1 | Nhận & hiển thị/truy xuất dữ liệu tối thiểu **04/06 thiết bị** | Farm State Store nhận cả **6/6** | `GET /api/v1/state/farm` → đủ 6 device, ≥4 `FRESH` | ☐ |
| 2 | Tối thiểu **03 Agent**, một tác vụ cần **≥02 Agent phối hợp** | **7 agent**; Kịch bản 1 huy động **6** | `GET /api/v1/agent/sessions/{id}` → đếm `agent` khác nhau trong `agent_events` | ☐ |
| 3 | ≥1 kế hoạch/quyết định **dùng dữ liệu MQTT** | Mọi quyết định bắt buộc có `evidence_refs` ≥1, truy về `topic_raw`/`topic_p` | `decisions[].evidence_refs` khác rỗng; `evidence_ledger[].source_topic` là topic MQTT | ☐ |
| 4 | Có **Tool/API** tạo lịch tưới / nhiệm vụ / thông báo / báo cáo | 4 tool ghi: `create_irrigation_schedule`, `create_inspection_ticket`, `send_notification`, `generate_report` | `GET /api/v1/plans` và `/tasks` trả về bản ghi thật | ☐ |
| 5 | **Có verification sau hành động** | Verifier đọc lại từ store + so khớp field + audit evidence | `VerificationResult.read_back_ok=true`, `field_matches>0`; xoá thủ công đối tượng khỏi DB rồi chạy lại → phải ra `MISMATCH` | ☐ |
| 6 | Giao diện **không vỡ layout trên điện thoại** | Trách nhiệm frontend — 4 khối ở [04](04-integration-guide.md#32-bốn-khối-ui-mà-btc-chấm-điểm) | DevTools 375×667 (iPhone SE), không cuộn ngang | ☐ |

> **Cách kiểm mục 5 là quan trọng nhất.** Verification của code hiện tại trên `main` sẽ trả `VERIFIED` kể cả khi bản ghi không tồn tại. Bài kiểm "xoá bản ghi rồi chạy lại" phân biệt được xác minh thật với xác minh giả — và nếu giám khảo hỏi "làm sao biết verification không phải giả", đây là câu trả lời demo được tại chỗ.

---

## Đối chiếu tiêu chí chấm điểm

### Vòng bảng

| Tiêu chí | % | Nằm ở đâu |
|---|---|---|
| Xử lý dữ liệu thực tế | 25 | MQTT BTC → Redpanda → watermark + windowing → Farm State Store với nhãn độ mới; Partial Mode xử lý dữ liệu gián đoạn thật |
| Hiệu quả AI | 25 | 2 tầng: **LLM đa agent** thật sự ra quyết định (không phải viết văn) + **lớp ML định lượng** (ET0 Hargreaves, gradient boosting, Isolation Forest, chẩn đoán hiệu suất bơm) |
| Kiến trúc & Tích hợp | 20 | Microservice + event-driven; agent-core cách ly, giao tiếp qua hợp đồng; provider LLM đổi bằng 1 biến env |
| Phù hợp Domain & UX | 15 | Trace agent live, evidence dưới mỗi quyết định, khu phê duyệt, chỉ báo độ mới; đúng 6 thiết bị đề bài |
| Ý tưởng & Pitching | 15 | **AI chạy hoàn toàn offline tại nông trại** — không internet, không API key, không rate limit |

### Chung kết

| Tiêu chí | % | Nằm ở đâu |
|---|---|---|
| Độ hoàn thiện | 25 | Chu trình đủ: nhận yêu cầu → đọc IoT → phân công → phối hợp → Tool/API → verification → báo cáo |
| Năng lực phân tích AI | 25 | Nhiều giả thuyết khi dữ liệu chưa phân định được (KB2); khoảng tin cậy nới rộng khi thiếu cảm biến (KB3); bóc tách thành phần lượng nước |
| Độ tin cậy & An toàn | 20 | Policy Gate tất định · human-in-the-loop cho hành động lớn · verification đọc lại thật · không thể bịa số ở tầng cấu trúc |
| Sáng tạo | 15 | Evidence Ledger; LLM 3B local mà vẫn đa agent tin cậy nhờ "LLM đề xuất, code định đoạt" |
| Demo & Phản biện | 15 | Trace live cho thấy bước nào AI quyết, bước nào code gác; bảng benchmark local vs cloud ([08](08-eval-harness.md)) |

---

## Câu hỏi phản biện dự kiến

| Câu hỏi | Trả lời |
|---|---|
| *"Sao biết đây không phải rule-based?"* | Lượng nước từ mô hình ET0 Hargreaves + gradient boosting có khoảng tin cậy, không phải ngưỡng. Chẩn đoán bơm dựa trên hiệu suất so với đường nền học được của chính thiết bị. LLM chọn agent, cân nhắc đánh đổi và xếp ưu tiên — không phải viết lại kết quả đã quyết sẵn. Có **3 luật** rule-based được giữ có chủ đích: kiểm tra nhất quán liên thiết bị, dán nhãn rõ, không phải nguồn quyết định chính. |
| *"Model 3B thì làm được gì?"* | Nó không được giao thứ nó làm không nổi. Mọi phép tính, mọi ràng buộc an toàn, mọi xác minh đều nằm trong code. LLM lo phân loại, phối hợp, phán đoán đánh đổi và diễn đạt — đúng phần nó mạnh. Có bộ eval 15 case đo được điều này. |
| *"Verification có phải chỉ là in ra 'đã xác minh'?"* | Xoá bản ghi khỏi DB rồi chạy lại — hệ thống trả `MISMATCH`. Demo được tại chỗ. |
| *"Nếu AI quyết định sai thì sao?"* | Nó có thể **đề xuất** sai nhưng không thể **thực thi** sai. Policy Gate tất định chặn: bồn dưới 20%, bơm FAULT, vượt 500L phải người duyệt, chặn trên tuyệt đối 2000L. |
| *"Vì sao 7 agent chứ không phải 3?"* | Mỗi agent sở hữu bộ tool riêng và chặn một kiểu lỗi cụ thể — [bảng ở 01](01-architecture.md#4-roster-agent--và-vì-sao-từng-agent-thực-sự-cần-thiết) nêu rõ bỏ agent nào thì hỏng gì. |
| *"Sao không dùng GPT-4/Gemini cho mạnh?"* | Đổi được bằng 1 biến env và có bảng benchmark cả hai. Nhưng chạy offline là **lựa chọn domain**: nông trại vùng sâu không có internet ổn định, và hệ thống tưới không nên phụ thuộc rate limit của một API bên ngoài. |
