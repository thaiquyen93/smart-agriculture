from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
import os

def create_presentation():
    prs = Presentation()
    
    # Define slide layouts
    title_slide_layout = prs.slide_layouts[0]
    bullet_slide_layout = prs.slide_layouts[1]
    
    # SLIDE 1: Title and Overview
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    subtitle = slide.placeholders[1]
    
    title.text = "AI-Driven Smart Operations Platform"
    subtitle.text = "Hệ thống Quản trị Vận hành Thông minh ứng dụng Enterprise IoT & AI Đa tác tử"
    
    slide = prs.slides.add_slide(bullet_slide_layout)
    shapes = slide.shapes
    title_shape = shapes.title
    body_shape = shapes.placeholders[1]
    
    title_shape.text = "Tổng quan Dự án (Project Overview)"
    
    tf = body_shape.text_frame
    tf.text = "Mục tiêu: Xây dựng nền tảng giám sát và vận hành thời gian thực (Real-time Control Room) dành cho hệ thống nông nghiệp/công nghiệp."
    
    p = tf.add_paragraph()
    p.text = "Mô hình Kiến trúc Cốt lõi: Cảm hứng từ chuẩn Enterprise IoT với cơ chế Event-Driven, Stream Processing & Multi-Agent AI."
    
    p = tf.add_paragraph()
    p.text = "Đặc điểm Nổi bật:"
    p.level = 0
    
    p = tf.add_paragraph()
    p.text = "Siêu tốc độ: Xử lý luồng dữ liệu thô độ trễ thấp (<1ms) qua Redpanda."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Thông minh: Phân tích gốc rễ vấn đề tự động với Gemini LLM."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Bền bỉ: Tự động kích hoạt Fallback ML Engine khi AI Cloud gặp sự cố, đảm bảo 100% Uptime."
    p.level = 1

    # SLIDE 2: Data & Stream Pipeline
    slide = prs.slides.add_slide(bullet_slide_layout)
    shapes = slide.shapes
    title_shape = shapes.title
    body_shape = shapes.placeholders[1]
    
    title_shape.text = "Kiến trúc Dữ liệu & Xử lý Luồng (Data & Stream Pipeline)"
    
    tf = body_shape.text_frame
    tf.text = "Tầng 1 - Ingestion (Thu thập):"
    
    p = tf.add_paragraph()
    p.text = "Dữ liệu cảm biến IoT đổ về qua MQTT/CoAP."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Sử dụng Redpanda Event Bus truyền hàng triệu sự kiện mỗi giây (Topic: sensor-raw)."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Tầng 2 - Stream Processing (Xử lý Luồng):"
    p.level = 0
    
    p = tf.add_paragraph()
    p.text = "Làm sạch và gom cụm dữ liệu trước khi nạp vào AI."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Watermarking: Đảm bảo không mất mát dữ liệu do độ trễ mạng chập chờn."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Sliding Windows: Gom dữ liệu theo chu kỳ (5-10s) tối ưu tính toán."
    p.level = 1

    # SLIDE 3: Multi-Agent AI Core
    slide = prs.slides.add_slide(bullet_slide_layout)
    shapes = slide.shapes
    title_shape = shapes.title
    body_shape = shapes.placeholders[1]
    
    title_shape.text = "Lõi Trí tuệ Nhân tạo Đa Tác tử (Multi-Agent AI Core)"
    
    tf = body_shape.text_frame
    tf.text = "Hệ thống kết hợp AI cục bộ và LLM Cloud để ra quyết định:"
    
    p = tf.add_paragraph()
    p.text = "Agent 1 (Anomaly Detector): Dùng Isolation Forest soi dữ liệu 24/7 phát hiện điểm bất thường."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Agent 2 (Risk Predictor): Dùng XGBoost Time-Series dự báo rủi ro trong 5-10 phút tới."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Agent 3 (Decision LLM - Gemini): Phân tích nguyên nhân sâu xa (Root Cause) khi có cảnh báo."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Fallback ML Engine: Dự phòng cục bộ (Local Rules/ML) tự động kích hoạt nếu mất kết nối Gemini."
    p.level = 1

    # SLIDE 4: Control Room Dashboard
    slide = prs.slides.add_slide(bullet_slide_layout)
    shapes = slide.shapes
    title_shape = shapes.title
    body_shape = shapes.placeholders[1]
    
    title_shape.text = "Trung tâm Điều hành & Hiển thị (Control Room Dashboard)"
    
    tf = body_shape.text_frame
    tf.text = "Công nghệ nền tảng: Dark-mode UI bằng React.js + TailwindCSS, FastAPI WebSocket cho độ trễ <100ms."
    
    p = tf.add_paragraph()
    p.text = "Tính năng Cốt lõi trên UI:"
    p.level = 0
    
    p = tf.add_paragraph()
    p.text = "Bản đồ Tương tác (Leaflet): Định vị các trạm IoT, cảnh báo đỏ khi xảy ra sự cố."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Biểu đồ Cửa sổ Trượt (Recharts): Vẽ chuỗi thời gian thực thay đổi liên tục."
    p.level = 1
    
    p = tf.add_paragraph()
    p.text = "Thẻ Hành động (Action Cards): Hiện cảnh báo AI và cho phép kích hoạt lệnh khắc phục ngay lập tức."
    p.level = 1
    
    # Save the presentation
    output_path = os.path.join(os.path.dirname(__file__), "AI_Operations_Platform_Presentation.pptx")
    prs.save(output_path)
    print(f"Presentation generated at: {output_path}")

if __name__ == '__main__':
    create_presentation()
