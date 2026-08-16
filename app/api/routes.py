from flask import Blueprint, request, jsonify
import uuid

from app.services.message_broker import broker

# Khởi tạo trực tiếp ML Model và Fuzzy Agent
from app.ml.models import SensorPredictorService
from app.fuzzy.agent import FuzzyAgent

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

    # Ánh xạ tên biến: Đầu vào của API -> Tên biến của LSTM Model
    # Ví dụ: user có thể gửi 'tank_level' hoặc 'level'. LSTM chỉ hiểu 'level'.
    api_to_ml_mapping = {
        'tank_level': 'level',
        'solar_radiation': 'lux'
    }
    
    # Ánh xạ ngược lại: LSTM Model -> Fuzzy Agent
    # Fuzzy Agent sử dụng 'tank_level' và 'solar_radiation' thay vì 'level' và 'lux'
    ml_to_fuzzy_mapping = {
        'level': 'tank_level',
        'lux': 'solar_radiation'
    }

    predicted_values = {}
    
    # 1. Dự báo dữ liệu (Predictive)
    for field, values in data.items():
        # Xử lý mapping tên biến
        ml_field = api_to_ml_mapping.get(field, field)
        
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
    fuzzy_input = {}
    for ml_field, pred_val in predicted_values.items():
        fuzzy_field = ml_to_fuzzy_mapping.get(ml_field, ml_field)
        fuzzy_input[fuzzy_field] = pred_val

    # Đưa vào FuzzyAgent
    try:
        fuzzy_output = fuzzy_agent.process(fuzzy_input)
    except Exception as e:
        return jsonify({"error": f"Fuzzy logic failed: {str(e)}"}), 500

    task_id = str(uuid.uuid4())
    
    # 3. Đóng gói JSON Output
    result = {
        "task_id": task_id,
        "input_data": data,
        "predictive": predicted_values,
        "fuzzy": fuzzy_output
    }

    # 4. (Đã gỡ bỏ Redis theo yêu cầu)

    # 5. Publish ra Output Topic
    from app.core.config import Config
    broker.publish_message(Config.OUTPUT_TOPIC, result)

    return jsonify({
        "status": "success",
        "task_id": task_id,
        "message": "Processed successfully, result sent to Topic and API",
        "result": result
    })


