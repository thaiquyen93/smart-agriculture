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

if __name__ == '__main__':
    unittest.main()
