import unittest
from app import create_app

class TestAPI(unittest.TestCase):
    def setUp(self):
        # Thiết lập môi trường test
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_health_check(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'ok')

    def test_process_no_data(self):
        response = self.client.post('/api/process', json={})
        self.assertEqual(response.status_code, 400)

    def test_process_invalid_array_length(self):
        # Thiếu dữ liệu, mảng chỉ có 3 phần tử thay vì 10
        response = self.client.post('/api/process', json={
            "temperature": [25.1, 25.2, 25.3]
        })
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("must be a list of exactly 10 values", data['error'])

    def test_process_valid_data(self):
        # Dữ liệu hợp lệ với 10 phần tử
        payload = {
            "temperature": [25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8, 25.9, 26.0],
            "tank_level": [80, 81, 80, 79, 78, 80, 81, 80, 80, 80]
        }
        response = self.client.post('/api/process', json=payload)
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertEqual(data['status'], 'success')
        
        result = data['result']
        self.assertIn('input_data', result)
        self.assertIn('predictive', result)
        self.assertIn('fuzzy', result)
        
        # Đảm bảo LSTM đã ánh xạ tank_level -> level
        self.assertIn('level', result['predictive'])
        self.assertIn('temperature', result['predictive'])
        
        # Đảm bảo Fuzzy vẫn giữ nguyên kết quả cấu trúc
        self.assertIn('quyết định', result['fuzzy'])
        self.assertIn('nguyên nhân quyết định', result['fuzzy'])

if __name__ == '__main__':
    unittest.main()
