# SMURF `agent-core` — Multi-Agent AI cho Track B: Smart Agriculture

> Nhánh: `feat/agent-core` · Service: `services/agent-core/` (chưa có code, mới có hợp đồng)
> Người phụ trách: mảng Multi-Agent AI

---

## Tóm tắt 1 trang

`agent-core` là service Multi-Agent AI của SMURF. Nó **không** thay thế `services/ai-agent/` — nó là một service riêng, cách ly, giao tiếp với phần còn lại của hệ thống **chỉ qua Kafka topic và HTTP**, để 5 người làm song song không giẫm chân nhau.

**Nó làm gì:** nhận một yêu cầu tiếng Việt của người quản lý nông trại ("chuẩn bị kế hoạch tưới cho khu A hôm nay"), đọc dữ liệu IoT thật từ 6 thiết bị, phối hợp nhiều Agent để lập kế hoạch, gọi Tool/API để tạo lịch tưới / phiếu kiểm tra / thông báo, **đọc lại để xác minh**, rồi trả về bản tin kèm **bằng chứng dữ liệu cho từng quyết định**.

**Nguyên tắc cốt lõi — "LLM đề xuất, code định đoạt":** LLM lo phần phán đoán (phân loại yêu cầu, chọn agent, cân nhắc nông học, viết văn). Code lo phần không được sai (mọi phép tính số, ràng buộc an toàn, thực thi tool, xác minh). Xem [ADR-002](adr/ADR-002-workflow-over-agent.md).

**LLM:** qwen2.5-3b-instruct chạy local qua LM Studio. Đổi sang Gemini bằng **1 biến env**. Xem [ADR-001](adr/ADR-001-llm-provider-strategy.md).

---

## Đọc file nào?

| Bạn là | Đọc |
|---|---|
| **Thành viên khác cần cắm vào agent-core** | [04-integration-guide.md](04-integration-guide.md) → rồi [03-contracts.md](03-contracts.md). Chỉ cần 2 file này. |
| Người mới vào nhánh, muốn hiểu vì sao thiết kế như vậy | [01-architecture.md](01-architecture.md) |
| Người sẽ viết code agent | [02-agents-and-tools.md](02-agents-and-tools.md) |
| Người làm ML / chủ nhánh `ai-fuzzy-branch` | [05-ml-interfaces.md](05-ml-interfaces.md) |
| Người chuẩn bị demo & phản biện trước giám khảo | [06-scenarios-and-acceptance.md](06-scenarios-and-acceptance.md) + [08-eval-harness.md](08-eval-harness.md) |

## Mục lục đầy đủ

| File | Nội dung |
|---|---|
| [01-architecture.md](01-architecture.md) | Bối cảnh, vấn đề của code hiện tại, quyết định kiến trúc theo skill `ai-agent-architecture-advisor`, sơ đồ, roster agent |
| [02-agents-and-tools.md](02-agents-and-tools.md) | Đặc tả từng agent + tool catalog chuẩn ACI |
| [03-contracts.md](03-contracts.md) | JSON Schema, Kafka topic, REST/SSE endpoint — **hợp đồng với các service khác** |
| [04-integration-guide.md](04-integration-guide.md) | Việc cụ thể từng thành viên phải làm, setup LM Studio, thứ tự khởi động |
| [05-ml-interfaces.md](05-ml-interfaces.md) | Interface + baseline cho lớp ML định lượng |
| [06-scenarios-and-acceptance.md](06-scenarios-and-acceptance.md) | 3 kịch bản BTC → trace kỳ vọng → checklist nghiệm thu |
| [07-roadmap.md](07-roadmap.md) | Milestone, backlog, thứ tự làm |
| [08-eval-harness.md](08-eval-harness.md) | Bộ đo để quyết định local vs Gemini bằng số |
| [adr/](adr/) | 3 quyết định kiến trúc quan trọng và lý do |

---

## ⚠️ Ba việc cần team xử lý (không thuộc agent-core nhưng chặn agent-core)

1. **BUG CHẶN PIPELINE — ưu tiên cao nhất.** [processor.py:79](../../services/ingestion-stream-engine/src/processor.py#L79) đọc `agg['metrics']['temp_avg']`, nhưng thiết bị Track B gửi field `temperature` → aggregator sinh `temperature_avg`. `KeyError` ném ra **trước** lệnh `producer.send()` → **không window nào tới được `topic_p`/`topic_h`**. Toàn bộ tầng AI đang đói dữ liệu. Chi tiết & cách sửa: [04-integration-guide.md](04-integration-guide.md#việc-của-data--stream-engine).

2. **`topic_alerts` luôn rỗng.** `aggregate_window_records()` không hề sinh field `anomalies`, nên `agg.get("anomalies", [])` luôn `[]`.

3. **`.env` đang được commit kèm mật khẩu MQTT thật** (`MQTT_PASSWORD`, `MQTT_TEST_KEY`). Repo là public trên GitHub. Chủ repo cân nhắc chuyển sang `.env.example` + `.gitignore`.

---

## Trạng thái hiện tại

- [x] Chốt kiến trúc & pattern
- [x] Tài liệu + hợp đồng tích hợp
- [x] `.env.example`
- [ ] Code service `services/agent-core/` — **phiên sau**

Xem [07-roadmap.md](07-roadmap.md) để biết thứ tự triển khai.
