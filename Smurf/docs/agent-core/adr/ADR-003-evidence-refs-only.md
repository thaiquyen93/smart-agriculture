# ADR-003 — LLM không phát ra số liệu cảm biến, chỉ tham chiếu `evidence_id`

**Trạng thái:** Chấp nhận · **Ngày:** 2026-08-16

## Bối cảnh

BTC quan sát rõ ràng ở Kịch bản 3: *"Không bịa giá trị mới"*. Và ở yêu cầu UX chung: *"Thể hiện rõ dữ liệu IoT đã ảnh hưởng đến quyết định nào"*. Cách tiếp cận thông thường là dặn trong system prompt ("đừng bịa số liệu") — biện pháp này yếu, đặc biệt với model 3B, vốn dễ "làm tròn", "nội suy", hoặc lặp lại sai một con số đã thấy trước đó trong hội thoại.

## Quyết định

Làm cho việc bịa số **bất khả thi về mặt cấu trúc**, không chỉ bị cấm bằng lời:

1. Mọi lần tool đọc dữ liệu cảm biến ghi một **Evidence Record** (`evidence_id`, `device_id`, `metric`, `value_text`, `unit`, `observed_at`, `age_seconds`, `freshness`, `source_topic`).
2. Kết quả trả về cho LLM là bảng markdown, mỗi giá trị đi kèm `evidence_id` của chính nó.
3. **JSON schema đầu ra của mọi agent không có field kiểu số cho giá trị cảm biến.** Muốn nhắc tới một số đo, LLM chỉ có thể ghi `evidence_refs: ["EV-8821"]`.
4. **Code** — không phải LLM — resolve `evidence_id` thành số liệu thật khi dựng bản tin cuối cùng.
5. Verifier chạy `audit_evidence`: quét output tìm token số không truy được về evidence nào (`unsourced_numbers`); khác rỗng → `MISMATCH`.

## Vì sao đây là quyết định kiến trúc, không phải quy tắc prompt

So sánh hai cách chặn:

| | Chặn bằng prompt | Chặn bằng cấu trúc (đã chọn) |
|---|---|---|
| Cơ chế | "Đừng bịa số" trong system prompt | Schema không có chỗ cho số trần |
| Độ tin cậy với model 3B | Thấp — dễ bị bỏ qua dưới áp lực điền đủ trường | Cao — không có trường nào để điền số vào |
| Khả năng kiểm tra | Chỉ đọc output bằng mắt | Verifier quét tự động, có tiêu chí đúng/sai rõ |
| Chịu được prompt injection trong `user_request` | Không | Có — injection không thể tạo ra `evidence_id` không tồn tại |

Nguyên tắc rộng hơn: **đừng dặn model đừng làm việc mà cấu trúc dữ liệu không thể ngăn nó làm.** Đây cũng là tinh thần "poka-yoke" mà skill nhấn mạnh ở phần thiết kế tool — áp dụng ở đây cho toàn bộ luồng dữ liệu, không chỉ tham số một tool.

## Vì sao gắn liền với Partial Mode ([01-architecture.md §5.2](../01-architecture.md#52-partial-mode--kịch-bản-3-dữ-liệu-hiện-trường-bị-gián-đoạn))

Thiết bị `OFFLINE` không phát Evidence Record mới (chỉ có bản ghi "vắng mặt", `is_absence_record=true`, không mang giá trị). Do đó một quyết định `confident` không thể nào trích dẫn được số liệu từ thiết bị đã chết — không phải vì LLM được dặn tránh, mà vì không có `evidence_id` nào tồn tại để trích dẫn. Đây là cách Kịch bản 3 được đáp ứng ở tầng cấu trúc thay vì tầng lời nhắc.

## Đánh đổi đã chấp nhận

| Đánh đổi | Chấp nhận vì |
|---|---|
| Prompt phức tạp hơn (LLM phải học thao tác qua evidence_id thay vì số trực tiếp) | Đổi lại được một đảm bảo kiểm tra được bằng code, không phụ thuộc việc model có "nghe lời" hay không |
| Cần thêm bước resolve ở tầng render | Chi phí code một lần, không lặp lại theo từng phiên |
| Narrative Agent bị giới hạn không được "diễn đạt lại" số liệu theo ý riêng | Đây chính là mục đích — nó chỉ được viết văn quanh số liệu đã chốt, không được tạo ra số mới |

## Hệ quả

- Mọi schema mới cho agent phải tuân quy tắc này — thêm vào checklist review ở [03-contracts.md §1](../03-contracts.md#1-quy-tắc-tập-giao-schema--bắt-buộc)
- Bộ eval ([08-eval-harness.md](../08-eval-harness.md)) có tiêu chí #3 kiểm trực tiếp điều này trên mọi case, mọi provider
- Nếu một agent mới thực sự cần "tính toán" ra một con số mới (không phải trích dẫn), con số đó phải đến từ một tool (mã hoá cứng phép tính, xem [05-ml-interfaces.md](../05-ml-interfaces.md)), rồi tool đó tự phát Evidence Record cho chính kết quả của mình — không có ngoại lệ "LLM tự tính nhanh trong đầu"
