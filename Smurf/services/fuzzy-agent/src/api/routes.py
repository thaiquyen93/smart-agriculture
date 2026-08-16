from flask import Blueprint, request, jsonify
import uuid

from src.services.message_broker import broker

# Khởi tạo trực tiếp ML Model và Fuzzy Agent
from src.ml.models import SensorPredictorService
from src.fuzzy.agent import FuzzyAgent

api_bp = Blueprint('api', __name__)
predictive_service = SensorPredictorService()
fuzzy_agent = FuzzyAgent()

# Khởi chạy luồng consume message từ RabbitMQ khi ứng dụng start
broker.start_consumer_thread()

@api_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "AI Backend is running"})

@api_bp.route('/process', methods=['POST'])
def process_data():
    """
    Endpoint nhận dữ liệu time-series (mảng 10 phần tử cho mỗi cảm biến).
    Dự đoán ra 1h tới, và đưa vào điều khiển mờ (Fuzzy).
    """
    data = request.json
    if not data:
        return jsonify({"error": "No input data provided"}), 400

    # Các trường dữ liệu bây giờ hoàn toàn đồng nhất giữa API, ML và Fuzzy Logic:
    # soil_moisture, temperature, humidity, flow_rate, power, ph, level, lux

    predicted_values = {}
    
    # 1. Dự báo dữ liệu (Predictive)
    for field, values in data.items():
        # Xử lý mapping tên biến (đã đồng nhất)
        ml_field = field
        
        # Bỏ qua các trường không thuộc dữ liệu cảm biến (ví dụ: client_id, timestamp...)
        if ml_field not in predictive_service.sensor_fields:
            continue
            
        # [Validation] Bắt buộc phải có đúng 10 phần tử
        if not isinstance(values, list) or len(values) != 10:
            return jsonify({
                "error": f"Field '{field}' must be a list of exactly 10 values for prediction."
            }), 400
            
        # Gọi ML Model dự đoán
        try:
            predicted_val = predictive_service.predict(ml_field, values)
            predicted_values[ml_field] = predicted_val
        except Exception as e:
            return jsonify({"error": f"Prediction failed for field '{field}': {str(e)}"}), 500

    if not predicted_values:
        return jsonify({"error": "No valid sensor data provided for prediction."}), 400

    # 2. Xử lý logic mờ (Fuzzy Logic) dựa trên kết quả DỰ BÁO
    fuzzy_input = predicted_values.copy()

    # Đưa vào FuzzyAgent
    try:
        fuzzy_output = fuzzy_agent.process(fuzzy_input)
    except Exception as e:
        return jsonify({"error": f"Fuzzy logic failed: {str(e)}"}), 500

    task_id = str(uuid.uuid4())
    
    # 3. Đóng gói JSON Output
    result = {
        "task_id": task_id,
        "predictive": predicted_values,
        "fuzzy": fuzzy_output
    }

    # 4. (Đã gỡ bỏ Redis theo yêu cầu)

    # 5. Publish ra Output Topic
    from src.core.config import Config
    broker.publish_message(Config.OUTPUT_TOPIC, result)

    return jsonify({
        "status": "success",
        "task_id": task_id,
        "message": "Processed successfully, result sent to Topic and API",
        "result": result
    })


