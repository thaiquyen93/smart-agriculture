# ADR-002 — Workflow có chặn thay vì Agent tự do

**Trạng thái:** Chấp nhận · **Ngày:** 2026-08-16

## Bối cảnh

Skill `ai-agent-architecture-advisor` (dựa trên "Building Effective AI Agents", Anthropic) phân biệt **Workflow** (LLM+tool chạy theo đường code định sẵn, ưu tiên dự đoán được) và **Agent** (LLM tự quyết bước và cách dùng tool, ưu tiên linh hoạt, chấp nhận rủi ro lỗi dồn tích qua nhiều bước).

Track B đòi hỏi phối hợp đa agent qua một tập subtask **không cố định trước** (khu nào, thiết bị nào chết, cần hỏi gì) — điều thường ngả về phía Agent. Nhưng LLM nền tảng là **qwen2.5-3b-instruct**, và hành động cuối (bơm nước) có rủi ro vật lý thật.

## Quyết định

Chọn **hybrid nghiêng Workflow**: khung điều phối là code tất định, nhưng chèn các điểm quyết định do LLM đảm nhiệm, mỗi điểm chỉ làm đúng một việc hẹp. Cụ thể, ghép 4 pattern:

| Tầng | Pattern | Giới hạn cứng |
|---|---|---|
| Router | Routing | 1 lời gọi, phân loại vào 5 nhãn đóng |
| Coordinator | Orchestrator-workers | Menu worker **đóng** (3 loại cố định), tối đa **2** vòng dispatch |
| Workers | Parallelization | 3 worker chạy song song, mỗi worker menu tool ≤ 4 |
| Verifier | Evaluator-optimizer | Tối đa **1** lần retry, sau đó escalate cho người |

Nguyên tắc bao trùm: **"LLM đề xuất, code định đoạt".**

| Giao cho LLM | Giữ trong code |
|---|---|
| Phân loại yêu cầu, chọn worker, cân nhắc đánh đổi, viết văn | Mọi phép tính số, Policy Gate an toàn, thực thi tool, verification |

## Vì sao không chọn Agent tự do

1. **Lỗi dồn tích quá nhanh ở 3B.** Skill cảnh báo agent tự do phù hợp trong "môi trường đáng tin cậy" vì rủi ro lỗi dồn tích qua nhiều bước. Với model 3B, tốc độ dồn lỗi đủ nhanh để phá demo trong một phiên duy nhất.
2. **Rủi ro vật lý thật.** Lệnh tưới sai không phải một câu trả lời sai vô hại — nó tốn nước thật, có thể làm hỏng cây, và trong kịch bản mở rộng có thể liên quan tới máy bơm chạy khô. Không giao quyền quyết định cuối cho một model chưa đủ tin cậy.
3. **Predictability cần cho demo.** Giám khảo cần thấy được một chu trình rõ ràng lặp lại được — không phải một agent có thể đi 3, 7, hay 15 bước tuỳ hứng.

## Vì sao không chọn Workflow thuần (như code hiện tại trên `main`)

Code hiện tại (`farm_coordinator_agent.py` và 4 file còn lại) là workflow thuần — pipeline `if/else` 5 bước cố định, không có LLM tham gia quyết định nào. Đây chính là thứ BTC nói sẽ đánh trượt (*"cảnh báo bằng điều kiện cố định (rule-based)"*), và không đáp ứng được việc "phối hợp Agent" theo nghĩa thật — số bước, agent nào tham gia, cần hỏi gì đều đã biết trước khi chạy.

## Vì sao không dùng native tool-calling API

LM Studio hỗ trợ `tools` API kiểu OpenAI, nhưng nó không ổn định ở mức model 3B — dễ gọi sai tên tool, sai tham số, hoặc không gọi khi cần. Thay vào đó: mỗi bước dùng `response_format: json_schema` (structured output) để ép hình dạng đầu ra, và **code** tự dispatch tool dựa trên trường đã được điền. Việc này chuyển gánh nặng "gọi đúng tool" từ khả năng suy luận của model sang một cấu trúc if/else đơn giản mà code luôn làm đúng.

## Hệ quả

- Thêm một loại yêu cầu mới → thêm một nhánh Router + có thể thêm một worker, không phải thiết kế lại vòng lặp
- Giới hạn 2 vòng dispatch nghĩa là một số yêu cầu phức tạp sẽ bị cắt sớm và chuyển `PARTIAL` — chấp nhận được, vì minh bạch về giới hạn tốt hơn một agent chạy vô định
- Khi chuyển sang Gemini ([ADR-001](ADR-001-llm-provider-strategy.md)), giới hạn này được nới (`GEMINI_MAX_DISPATCH_ROUNDS=4`) chứ không bỏ hẳn — Policy Gate và Verifier bằng code vẫn giữ nguyên bất kể provider
