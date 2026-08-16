# 🧪 THỬ NGHIỆM KIỂM CHỨNG LƯU TRỮ REDPANDA TRÊN Ổ CỨNG

Thư mục này giúp bạn tự tay kiểm chứng xem Redpanda thực sự lưu trữ dữ liệu dạng file `.log` như thế nào trên ổ đĩa của bạn thông qua kỹ thuật **Bind Mount**.

---

## 🚀 CÁCH CHẠY THỬ NGHIỆM (3 BƯỚC):

### Bước 1: Khởi động Redpanda Test
Mở Terminal tại thư mục `test_server` và gõ:
```bash
docker compose up -d
```
*(Lúc này bạn sẽ thấy thư mục `storage/` tự động xuất hiện ngay trong thư mục `test_server` trên máy bạn!)*

---

### Bước 2: Bắn dữ liệu mẫu vào Redpanda
Gõ lệnh:
```bash
python producer.py
```
*(Script này sẽ gửi 10 bản tin JSON vào topic `test-topic`)*

---

### Bước 3: Tận mắt kiểm tra các file dữ liệu trên máy bạn!
Mở File Explorer trên Windows, vào đường dẫn:
```text
d:\Cac_Cuoc_Thi\Seal_Hackathon_SU26\test_server\storage\kafka\test-topic-0\
```

Bạn sẽ thấy các file vật lý xuất hiện:
1. **`00000000000000000000.log`**: Đây chính là file **chứa toàn bộ 10 bản tin JSON thật** được ghi tuần tự (Append-Only) trên đĩa cứng của bạn!
2. **`00000000000000000000.index`**: File chỉ mục Offset để Redpanda tìm kiếm cực nhanh.

---

## 🧹 DỌN DẸP SAU KHI HỌC XONG:
Khi đã hiểu rõ, bạn chỉ cần gõ:
```bash
docker compose down
```
Sau đó bạn có thể **xóa thẳng tay thư mục `test_server` này đi** mà không ảnh hưởng gì đến dự án `Smurf`!
