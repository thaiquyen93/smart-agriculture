# ADR-001 — Chiến lược nhà cung cấp LLM: local 3B trước, giữ đường nâng cấp Gemini

**Trạng thái:** Chấp nhận · **Ngày:** 2026-08-16

## Bối cảnh

`agent-core` cần một LLM để phân loại yêu cầu, phối hợp agent, cân nhắc đánh đổi nông học, và viết bản tin tiếng Việt. Người phụ trách chọn dùng **qwen2.5-3b-instruct chạy local qua LM Studio** (`http://localhost:1234/v1`) để build và test, với dự định có thể chuyển sang Gemini nếu kết quả tốt hoặc khi cần sức mạnh hơn cho vòng chung kết.

## Quyết định

1. LLM mặc định: **qwen2.5-3b-instruct** qua LM Studio, endpoint OpenAI-compatible.
2. Kiến trúc client là một **protocol** `LLMClient` với **một** implementation `OpenAICompatClient`, tham số hoá bằng `base_url` / `model` / `api_key`.
3. Provider chọn qua biến `LLM_PROFILE` (`local` | `gemini`), mỗi profile có bộ tham số hành vi riêng (số vòng dispatch, bật/tắt native tool-calling).
4. Thiết kế prompt/schema theo "sàn 3B": nếu 3B làm được thì model mạnh hơn chắc chắn làm được — không ràng buộc ngược lại.

## Vì sao local trước

- **Chi phí & rate limit bằng không** trong lúc phát triển — build/test lặp đi lặp lại không lo hết quota.
- **Offline hoàn toàn** — không phụ thuộc kết nối internet lúc demo. Với domain nông trại, đây là điểm phù hợp thật, không phải biện minh.
- **Buộc thiết kế phải kỷ luật.** Một model yếu hơn không tha thứ cho prompt mơ hồ hay menu tool quá tải — thiết kế ra đời dưới ràng buộc này ("LLM đề xuất, code định đoạt", xem [ADR-002](ADR-002-workflow-over-agent.md)) sẽ *chắc chắn* chạy tốt hơn khi chuyển sang model mạnh hơn.

## Vì sao vẫn giữ đường nâng cấp Gemini, không khoá cứng vào local

LM Studio và Gemini **cùng nói giao thức OpenAI-compatible**:

| | LM Studio | Gemini |
|---|---|---|
| `base_url` | `http://localhost:1234/v1` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| SDK | `openai` | `openai` |
| Chat completions + streaming | ✅ | ✅ |
| `response_format` json_schema | ✅ | ✅ |
| Function calling | ✅ | ✅ |

Chuyển provider chỉ cần đổi 3 biến (`base_url`, `model`, `api_key`) — **miễn phí về mặt kiến trúc**, miễn là tuân thủ 2 kỷ luật dưới đây.

## Hai kỷ luật bắt buộc để giữ tính khả chuyển

**1. Schema JSON viết ở phần giao của hai bên.** LM Studio ép qua GBNF (llama.cpp), Gemini ép qua `responseSchema` — hai tập con khác nhau của JSON Schema. Quy tắc bắt buộc (chi tiết ở [03-contracts.md §1](../03-contracts.md#1-quy-tắc-tập-giao-schema--bắt-buộc)): object phẳng, cấm `$ref`/`anyOf`/`oneOf`/`allOf`, `additionalProperties: false`, `required` tường minh.

**2. Đặc tính riêng của provider nằm trong adapter, không rò ra code agent.** `reasoning_effort`/`thinking_budget` (Gemini) hay context length/`n_gpu_layers` (LM Studio) không được xuất hiện ngoài `OpenAICompatClient`. Agent chỉ thấy `llm.complete(prompt, schema) -> dict`.

Viết đúng hai điều này ngay từ đầu thì nâng cấp provider là đổi cấu hình, không phải viết lại.

## Đánh đổi đã chấp nhận

| Đánh đổi | Chấp nhận vì |
|---|---|
| Model 3B yếu hơn đáng kể so với Gemini 2.5 Flash | Vai trò của nó bị giới hạn có chủ đích — không tính toán, không giữ trạng thái an toàn, không xác minh. Xem [ADR-002](ADR-002-workflow-over-agent.md) |
| Latency cao hơn cloud (~10–40s/phiên trên máy không GPU rời) | Bù bằng UI trace-live thay vì spinner chờ; có đường lui `LLM_PROFILE=gemini` cho buổi demo nếu cần |
| Lớp OpenAI-compat của Google Gemini còn ghi **beta** | Giữ `LLMClient` là protocol — nếu lớp compat có vấn đề, thêm `GeminiNativeClient` bằng SDK `google-genai` mà agent không cần biết |
| Native tool-calling của LM Studio kém ổn định ở 3B | Không dùng — dùng structured output (`response_format`) + code tự dispatch. Xem [ADR-002](ADR-002-workflow-over-agent.md) |

## Cách quyết định "ở lại local hay chuyển hẳn Gemini"

Không đoán — đo. Bộ eval 15 case ([08-eval-harness.md](../08-eval-harness.md)) chạy trên cả hai profile, chấm 5 tiêu chí tất định, ra bảng so sánh điểm + latency. Bảng đó là căn cứ quyết định, và cũng là vật liệu phản biện trước giám khảo.

## Hệ quả

- `services/agent-core/.env.example` có sẵn cả hai khối cấu hình profile (xem [04-integration-guide.md §7](../04-integration-guide.md#7-cấu-hình-agent-core))
- Mọi schema mới thêm sau này phải qua bước lint "tập giao" trước khi merge
- Chọn `gemini` cho buổi demo chính thức là quyết định vận hành, đưa ra dựa trên số đo, không phải mặc định kiến trúc
