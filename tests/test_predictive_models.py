import unittest
import numpy as np
from app.ml.models import SensorPredictorService

class TestPredictiveModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Khởi tạo Service 1 lần cho tất cả các test cases để tiết kiệm thời gian
        cls.service = SensorPredictorService(model_save_dir="models_test/")

    def test_initialization(self):
        # Kiểm tra xem đủ 8 models đã được khởi tạo chưa
        expected_fields = [
            "soil_moisture", "temperature", "humidity", 
            "flow_rate", "power", "ph", "level", "lux"
        ]
        for field in expected_fields:
            self.assertIn(field, self.service.models)

    def test_prediction_output_shape(self):
        # Đầu vào: 10 giá trị
        dummy_input = [20.0, 21.0, 20.5, 22.0, 21.5, 22.5, 23.0, 22.8, 23.5, 24.0]
        
        # Dự đoán cho 'temperature'
        prediction = self.service.predict("temperature", dummy_input)
        
        # Output phải là 1 số float duy nhất
        self.assertIsInstance(prediction, float)

    def test_invalid_input_length(self):
        # Đầu vào thiếu (ví dụ: 9 giá trị) sẽ raise ValueError
        dummy_input = [20.0] * 9
        
        with self.assertRaises(ValueError):
            self.service.predict("temperature", dummy_input)

    def test_invalid_field(self):
        dummy_input = [20.0] * 10
        with self.assertRaises(ValueError):
            self.service.predict("unknown_sensor", dummy_input)

    def test_training_pipeline(self):
        # Test huấn luyện nhanh 2 epochs cho một cảm biến
        dummy_train_data = []
        for _ in range(10):
            seq = np.random.rand(10).tolist()
            target = sum(seq) / 10.0
            dummy_train_data.append((seq, target))
            
        # Không nên throw exception
        try:
            self.service.train_model("humidity", dummy_train_data, epochs=2)
            success = True
        except Exception as e:
            success = False
            
        self.assertTrue(success, "Training pipeline failed for humidity")

if __name__ == '__main__':
    unittest.main()
