# 07 — Roadmap & Backlog

> Lập ngày **2026-08-16**. Ước lượng theo giờ công, chưa gắn ngày cụ thể — điền hạn thật khi biết lịch vòng bảng.

---

## Nguyên tắc thứ tự

**Dựng xương sống chạy được trước, làm sâu sau.** Một phiên agent đi hết chu trình với mô hình thô còn giá trị hơn nhiều mô hình tốt mà chưa nối được với nhau — vì rủi ro lớn nhất của bài này là tích hợp, không phải chất lượng mô hình.

Thứ tự dưới đây được sắp sao cho **sau M2 đã có thứ để demo**, và mọi milestone sau chỉ làm nó tốt hơn chứ không phải điều kiện cần.

---

## M0 — Nền tảng *(~3h)*

| # | Việc | Xong khi |
|---|---|---|
| 0.1 | Khung service `services/agent-core/`: `main.py`, `Dockerfile`, `requirements.txt`, `config.py` đọc profile | `docker compose up agent-core` không crash |
| 0.2 | `LLMClient` protocol + `OpenAICompatClient` + đọc profile từ env | Gọi được LM Studio, đổi `LLM_PROFILE` không đổi code |
| 0.3 | Lớp structured output: gửi `response_format` json_schema + retry 1 lần khi parse hỏng + fallback tất định | Ép được 3B trả JSON đúng schema ≥95% lượt |
| 0.4 | Lint schema theo "tập giao" ([03 §1](03-contracts.md#1-quy-tắc-tập-giao-schema--bắt-buộc)) chạy trong test | CI/test fail nếu ai đó thêm `anyOf` |
| 0.5 | `GET /health` | Trả cả khi LM Studio tắt (`llm_reachable: false`) |

> **0.3 là mục rủi ro nhất toàn dự án.** Nếu 3B không giữ nổi schema thì mọi thứ phía sau lung lay. Làm sớm, đo thật, biết sớm. Nếu tỉ lệ tệ → hoặc hạ độ phức tạp schema, hoặc cân nhắc model 7B.

---

## M1 — Mặt phẳng tri giác *(~4h)*

| # | Việc | Xong khi |
|---|---|---|
| 1.1 | Kafka consumer `topic_raw`/`topic_p`/`topic_h` → Farm State Store (in-memory + SQLite) | 6 thiết bị có state, cập nhật liên tục |
| 1.2 | Tính độ mới + `data_completeness` + nhãn FRESH/STALE/OFFLINE | `GET /api/v1/state/farm` đúng; ngắt simulator → chuyển OFFLINE sau 10 phút |
| 1.3 | Evidence Ledger: sinh `evidence_id`, ghi bản ghi, resolve ngược | Mỗi lần đọc dữ liệu sinh evidence truy được |
| 1.4 | 4 tool đọc của Field IoT Agent | Gọi trực tiếp bằng test, trả bảng markdown đúng |

⚠️ **Phụ thuộc ngoài:** M1 cần `topic_p` thực sự có dữ liệu → bug `temp_avg` ([04 §1.1](04-integration-guide.md#11--bug-đang-chặn-toàn-bộ-pipeline)) phải được sửa trước. Nếu chưa, tạm đọc thẳng `topic_raw` để không bị chặn.

---

## M2 — Xương sống agent *(~6h)* → **demo được từ đây**

| # | Việc | Xong khi |
|---|---|---|
| 2.1 | Router + fallback heuristic | 5 playbook phân loại đúng |
| 2.2 | Coordinator (orchestrator có chặn 2 vòng) | Dispatch đúng worker theo playbook |
| 2.3 | 3 worker agent + tool tương ứng (ML dùng bản thô: ET0 + suy giảm vật lý) | Chạy song song, trả findings kèm evidence |
| 2.4 | Action Agent + Policy Gate + 4 tool ghi | Tạo được `PLAN-...` thật; vượt ngưỡng → `PENDING_APPROVAL` |
| 2.5 | **Verifier thật** (read_back + diff + audit) | Xoá bản ghi khỏi DB → chạy lại ra `MISMATCH` |
| 2.6 | Narrative Agent + chặn số không nguồn | Bản tin tiếng Việt, mọi số truy được về evidence |
| 2.7 | `AgentEvent` phát ra Kafka + SSE | UI xem được trace live |
| 2.8 | REST: sessions, approvals, plans, tasks, state/farm | Postman chạy hết |

**Cổng nghiệm thu M2:** chạy trọn Kịch bản 1 đầu-cuối, ra kế hoạch đã xác minh kèm evidence.

---

## M3 — Chiều sâu AI *(~5h)*

| # | Việc | Xong khi |
|---|---|---|
| 3.1 | `SoilMoistureForecaster` gradient boosting + retrain nền | Sai số tốt hơn fallback vật lý trên dữ liệu giữ lại |
| 3.2 | `WaterDemandEstimator` đầy đủ (Hargreaves + Kc + khoảng tin cậy + breakdown) | Trả `breakdown` cộng đúng tổng |
| 3.3 | `PumpHealthDetector` (hiệu suất + robust z-score + phân loại triệu chứng) | Mô phỏng tắc lọc → ra `DEGRADED` + đúng triệu chứng |
| 3.4 | `AnomalyDetector` Isolation Forest + 3 luật nhất quán liên thiết bị | Kịch bản 2 bắt được "bơm chạy mà đất không ẩm lên" |
| 3.5 | `registry.py` + adapter cho `ai-fuzzy-branch` | Đổi env là đổi model |

---

## M4 — Vững & hoàn thiện *(~4h)*

| # | Việc | Xong khi |
|---|---|---|
| 4.1 | Partial Mode đầy đủ + tách `confident`/`needs_verification` | Kịch bản 3 chạy đúng |
| 4.2 | Human-in-the-loop hoàn chỉnh (treo phiên, resume sau approve) | Duyệt trên UI → phiên chạy tiếp |
| 4.3 | Bộ eval 15 case ([08](08-eval-harness.md)) | Chạy 1 lệnh, ra bảng điểm |
| 4.4 | Chạy eval trên cả 2 profile → bảng benchmark | Có số để quyết định local vs Gemini |
| 4.5 | Chịu lỗi: LM Studio chết, Kafka mất, model cold-start | Rút cáp giữa demo, hệ thống suy giảm chứ không sập |
| 4.6 | Tối ưu độ trễ (cache prompt, gộp call, song song hoá) | Kịch bản 1 < 20s trên máy demo |

---

## M5 — Chuẩn bị demo *(~2h)*

| # | Việc |
|---|---|
| 5.1 | Script dựng 3 kịch bản BTC (bao gồm nút "giết cảm biến" cho Kịch bản 3) |
| 5.2 | Tổng duyệt đầu-cuối theo [04 §8](04-integration-guide.md#8-thứ-tự-khởi-động-khi-demo) |
| 5.3 | Đi hết checklist nghiệm thu [06](06-scenarios-and-acceptance.md) |
| 5.4 | Chuẩn bị 6 câu phản biện + bảng benchmark |
| 5.5 | Phương án dự phòng: bản ghi hình phiên chạy thành công, phòng khi máy demo trục trặc |

---

## Tổng ước lượng

| Milestone | Giờ | Cộng dồn |
|---|---|---|
| M0 Nền tảng | 3 | 3 |
| M1 Tri giác | 4 | 7 |
| M2 Xương sống agent | 6 | 13 |
| M3 Chiều sâu AI | 5 | 18 |
| M4 Vững & hoàn thiện | 4 | 22 |
| M5 Demo | 2 | 24 |

**~24 giờ công.** Nếu bị ép thời gian: **M0→M2 là bắt buộc** (13h, đủ để nộp có sản phẩm). M3 quyết định điểm "Hiệu quả AI". M4 quyết định điểm "Độ tin cậy". M5 quyết định điểm "Demo & Phản biện".

---

## Rủi ro

| Rủi ro | Ảnh hưởng | Xử lý |
|---|---|---|
| 3B không giữ nổi JSON schema | Cao — chặn tất cả | Đo ở M0.3. Xử lý: hạ độ phức tạp schema → tăng retry → thử qwen2.5-7b → chuyển Gemini |
| `topic_p` vẫn rỗng vì bug chưa sửa | Cao — M1 chặn | Đã báo team ở [04 §1.1]. Dự phòng: đọc thẳng `topic_raw` |
| Model local quá chậm khi demo | Trung bình | M4.6 tối ưu; profile `gemini` là đường lui tức thì |
| MQTT BTC đổi format phút chót | Trung bình | Farm State Store parse phòng thủ, log field lạ thay vì crash |
| Trùng việc với `ai-fuzzy-branch` | Thấp | Ranh giới rõ ở [05](05-ml-interfaces.md): họ làm model, mình làm agent; giao tiếp qua ABC |
| Verification bị chê là giả | Thấp | M2.5 có bài kiểm xoá-bản-ghi, demo được tại chỗ |

---

## Việc chờ người khác

| Chờ ai | Việc | Chặn cái gì |
|---|---|---|
| Data/Stream | Sửa bug `temp_avg` | M1.1 |
| Web Backend | Thêm 5 topic + proxy SSE | Trace live trên UI (agent-core vẫn chạy được) |
| Web Frontend | 4 khối UI | Điểm UX |
| Database | 5 bảng mới | Lưu lịch sử (agent-core tự lưu SQLite riêng được) |

`agent-core` **không bị chặn hoàn toàn** bởi ai — nó có store riêng và API riêng, test độc lập được. Chỉ phần hiển thị cần các bạn khác.
