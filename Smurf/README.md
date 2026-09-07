# SMURF PLATFORM - AI-Driven Smart Agriculture Operations

> **Giải pháp Nông nghiệp Thông minh đa tác tử (Multi-Agent AI) với kiến trúc Event-Driven & Stream Processing.**
> Dự án tham gia **SEAL Hackathon Summer 2026 - Track B: Smart Agriculture**.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Architecture](https://img.shields.io/badge/Architecture-Event--Driven-orange)
![AI](https://img.shields.io/badge/AI-Multi--Agent-green)
![Status](https://img.shields.io/badge/Status-Hackathon_Ready-success)

---

## Giới thiệu Dự án

**Smurf Platform** là một nền tảng vận hành nông trại thông minh, kết hợp giữa mạng lưới IoT (Internet of Things), xử lý luồng sự kiện tốc độ cao (Stream Processing), và hệ thống Trí tuệ Nhân tạo đa tác tử (Multi-Agent AI). 

Hệ thống giải quyết bài toán cốt lõi của **Track B**: Hỗ trợ người quản lý nông trại phối hợp giữa điều kiện canh tác (đất, thời tiết), tài nguyên (nước, bơm) và nhân sự ngoài hiện trường để đưa ra các quyết định vận hành, lịch tưới tiêu và phản ứng khẩn cấp một cách tối ưu nhất.

## Tính năng Nổi bật

*   **Xử lý Dữ liệu Thời gian thực (Real-time Stream Processing):** Xử lý hàng nghìn sự kiện/giây từ cảm biến bằng Redpanda và Stream Engine với cơ chế Watermarking và Sliding Windows.
*   **Multi-Agent AI Core:** Phối hợp nhiều AI Agents (Farm Coordinator, Field IoT, Irrigation Planning, Resource Action) sử dụng **Google Gemini** và **Machine Learning Cục bộ (Fallback)** để chẩn đoán, ra quyết định và lập kế hoạch hoàn toàn tự động.
*   **Control Room Dashboard:** Giao diện điều khiển (React/Next.js) Dark-mode hiện đại, hiển thị biểu đồ real-time, bản đồ tương tác (Leaflet) và các Thẻ Hành động (Action Cards) tức thời.
*   **Độ tin cậy cao:** Có cơ chế ML Fallback Cục bộ (Isolation Forest, XGBoost) hoạt động độc lập kể cả khi mất kết nối Internet/LLM Cloud, đảm bảo hệ thống không bao giờ gián đoạn.

## Kiến trúc Hệ thống (Microservices)

Hệ thống được thiết kế theo chuẩn Enterprise IoT với 5 vi dịch vụ (Microservices) chạy trên nền tảng Docker:

1.  **Ingestion & Stream Engine (`services/ingestion-stream-engine`):** Lắng nghe dữ liệu thô từ MQTT Broker, xử lý Watermarking & Windowing và đưa vào Redpanda.
2.  **Multi-Agent AI Core (`services/ai-agent`):** Hệ thống não bộ của dự án. Gồm các tác tử AI chẩn đoán, dự báo, và ra quyết định.
3.  **Web Backend (`services/web-backend`):** FastAPI/NestJS server phát dữ liệu qua WebSocket (độ trễ <100ms) và cung cấp REST API.
4.  **Web Frontend (`services/web-frontend`):** Next.js UI Control Room, theo dõi trực quan và nhận lệnh điều hành.
5.  **Database Persistence (`services/database-saver`):** Lưu trữ dữ liệu lịch sử vào SQLite (WAL-mode)/TimescaleDB.

*(Tham khảo thêm chi tiết trong `software_architecture.md`)*

## Công nghệ Sử dụng

*   **Message Broker & Event Streaming:** Redpanda (Kafka-compatible), MQTT, CoAP.
*   **Backend & Data Processing:** Python (FastAPI), Node.js (NestJS).
*   **Frontend & UI:** React.js, Next.js, TailwindCSS, Recharts, Leaflet.
*   **AI & Machine Learning:** Google Gemini Flash API, Isolation Forest (Anomaly), XGBoost (Forecasting).
*   **Database:** SQLite / TimescaleDB.
*   **DevOps:** Docker, Docker Compose.

## Hướng dẫn Khởi chạy (Quick Start)

### Yêu cầu hệ thống
*   [Docker](https://docs.docker.com/get-docker/) và [Docker Compose](https://docs.docker.com/compose/install/).

### Cài đặt và Chạy hệ thống

1.  **Cấu hình môi trường:**
    Sao chép file `.env.example` thành `.env` (nếu chưa có) và cập nhật các thông số MQTT Broker, Gemini API Key.
    ```bash
    cp .env.example .env
    ```

2.  **Khởi động toàn bộ cụm Microservices (Dành cho Demo/Chấm thi):**
    Chỉ với 1 lệnh duy nhất tại thư mục gốc của dự án:
    ```bash
    docker compose up --build -d
    ```

3.  **Truy cập dịch vụ:**
    *   **Control Room Dashboard (Frontend):** `http://localhost:3000`
    *   **API & WebSocket Backend:** `http://localhost:8000`
    *   **Redpanda Console (Monitor Events):** `http://localhost:8088`

4.  **Tắt hệ thống:**
    ```bash
    docker compose down
    ```

## Phân công Đội thi (5 Thành viên)

*   **Member 1:** Ingestion & Redpanda Dev (Data Pipeline & MQTT).
*   **Member 2:** Stream Processing Dev (Watermarking & Windowing).
*   **Member 3:** AI & Fallback Engine Dev (Gemini Multi-Agent & ML).
*   **Member 4:** Frontend Control Room Dev (React/Next.js Dashboard).
*   **Member 5:** Backend Dev & Team Lead (FastAPI/WebSocket & Integration).

---
*Developed for SEAL Hackathon Summer 2026*
