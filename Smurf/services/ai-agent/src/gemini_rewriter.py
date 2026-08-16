import json
import logging
import time
from typing import Dict, Any
from src.config import ai_settings

logger = logging.getLogger("gemini_rewriter")

class GeminiHumanizerAgent:
    """
    Gemini LLM Re-writer Agent.
    Takes technical Inference Engine outputs (anomalies, root causes, decisions)
    and humanizes them into natural, professional Vietnamese operational reports.
    """
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if ai_settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=ai_settings.GEMINI_API_KEY)
                logger.info("✓ Gemini LLM Re-writer Agent initialized successfully")
            except Exception as e:
                logger.warning(f"Gemini client init warning: {e}")

    def humanize_report(self, inference_output: Dict[str, Any], predict_output: Dict[str, Any]) -> Dict[str, Any]:
        if not self.client or not ai_settings.GEMINI_API_KEY:
            # Fallback humanizer if API key unavailable
            return self._fallback_humanize(inference_output, predict_output)

        prompt = f"""
Bạn là Chuyên gia Khí tượng Thủy văn & Kỹ sư Vận hành Đô thị Thông minh.
Dưới đây là kết quả suy luận kỹ thuật thô từ hệ thống:

- Trạm: {inference_output.get('device_id')}
- Cấp độ rủi ro Fuzzy: {inference_output.get('fuzzy_level')}
- Bất thường ghi nhận: {json.dumps(inference_output.get('anomalies', []), ensure_ascii=False)}
- Nguyên nhân cốt lõi: {json.dumps(inference_output.get('root_causes', []), ensure_ascii=False)}
- Quyết định hành động: {json.dumps(inference_output.get('smart_decisions', []), ensure_ascii=False)}
- Dự báo xu hướng 6h: {predict_output.get('forecast_horizons', {}).get('6_hours')}

Hãy viết lại kết quả trên thành một bản tin dự báo & chỉ đạo vận hành mượt mà, chuyên nghiệp bằng tiếng Việt.
Trả về JSON thuần với cấu trúc:
{{
  "weather_condition": "Tên hình thái thời tiết chính",
  "risk_score": 85,
  "risk_level": "LOW|MODERATE|HIGH|CRITICAL",
  "synoptic_analysis": "Đoạn phân tích khí tượng chuyên sâu 2-3 câu bằng tiếng Việt",
  "smart_operational_decisions": ["Danh sách các chỉ đạo vận hành"]
}}
"""
        try:
            model_name = ai_settings.AI_MODEL_NAME or "gemini-2.5-flash"
            response = self.client.models.generate_content(model=model_name, contents=prompt)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            parsed = json.loads(text.strip())
            parsed["source"] = f"GEMINI_AI ({model_name})"
            parsed["station_id"] = inference_output.get("device_id")
            parsed["generated_at"] = time.time()
            return parsed
        except Exception as e:
            logger.warning(f"Gemini API error ({e}). Using fallback humanizer.")
            return self._fallback_humanize(inference_output, predict_output)

    def _fallback_humanize(self, inference_output: Dict[str, Any], predict_output: Dict[str, Any]) -> Dict[str, Any]:
        fuzzy_level = inference_output.get("fuzzy_level", "LOW")
        score = 85.0 if fuzzy_level == "CRITICAL" else (50.0 if fuzzy_level == "HIGH" else 15.0)
        return {
            "source": "HEURISTIC_OFFLINE_HUMANIZER",
            "station_id": inference_output.get("device_id"),
            "weather_condition": "Bão nhiệt đới mạnh" if fuzzy_level in ("CRITICAL", "HIGH") else "Thời tiết ổn định",
            "risk_score": score,
            "risk_level": fuzzy_level,
            "synoptic_analysis": f"Cảnh báo khí tượng: Trạm {inference_output.get('device_id')} ghi nhận bất thường. " + " ".join(inference_output.get("root_causes", [])),
            "smart_operational_decisions": inference_output.get("smart_decisions", []),
            "generated_at": time.time()
        }
