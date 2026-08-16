from flask import Blueprint, request, jsonify
import uuid
from app.core.redis_client import redis_client
from app.agents.orchestrator import MultiAgentOrchestrator
from app.services.message_broker import broker

api_bp = Blueprint('api', __name__)
orchestrator = MultiAgentOrchestrator()

# Khởi chạy luồng consume message từ RabbitMQ khi ứng dụng start
broker.start_consumer_thread()

@api_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "AI Backend is running"})

@api_bp.route('/process', methods=['POST'])
def process_data():
    """
    Endpoint cho phép nhận dữ liệu qua API, xử lý Multi-Agent, 
    lưu kết quả vào Redis và đồng thời đẩy ra Output Topic.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No input data provided"}), 400

    task_id = str(uuid.uuid4())
    data['task_id'] = task_id

    # 1. Chạy luồng Multi-Agent
    result = orchestrator.process(data)
    result['task_id'] = task_id

    # 2. Lưu kết quả vào Redis (Cache expire sau 1 giờ)
    redis_client.setex(f"task_result:{task_id}", 3600, str(result))

    # 3. Publish ra Output Topic
    from app.core.config import Config
    broker.publish_message(Config.OUTPUT_TOPIC, result)

    return jsonify({
        "status": "success",
        "task_id": task_id,
        "message": "Processed successfully, result sent to Topic and API",
        "result": result
    })

@api_bp.route('/result/<task_id>', methods=['GET'])
def get_result(task_id):
    """
    Lấy kết quả đã xử lý (từ input Topic hoặc API) lưu trong Redis
    """
    result = redis_client.get(f"task_result:{task_id}")
    if result:
        # Convert chuỗi string dict từ Redis sang JSON an toàn (Dùng eval hoặc json, ở đây dùng an toàn thì json)
        import ast
        try:
            return jsonify({"status": "success", "task_id": task_id, "result": ast.literal_eval(result)})
        except:
            return jsonify({"status": "success", "task_id": task_id, "result": result})
    return jsonify({"error": "Task not found"}), 404
