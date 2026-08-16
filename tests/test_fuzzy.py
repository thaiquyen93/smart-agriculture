import unittest
from app.fuzzy.agent import FuzzyAgent

class TestFuzzyAgent(unittest.TestCase):
    def setUp(self):
        # Khởi tạo FuzzyAgent cho mỗi test case
        self.fuzzy_agent = FuzzyAgent()

    def test_process_very_dry_hot(self):
        # Test Rule R_CTL_01: Very Dry, High tank, Low/Medium solar -> High flow
        data = {
            'soil_moisture': 5,      # Very Dry
            'tank_level': 80,        # High
            'solar_radiation': 1000, # Low
            'temperature': 25,
            'ph': 7.0,
            'pump_power': 50, # Nominal (avoids R_ANO_03 'Off' anomaly)
            'pump_flow': 50   # Normal
        }
        result = self.fuzzy_agent.process(data)
        
        self.assertIn('mã_luật', result)
        self.assertEqual(result['mã_luật'], 'R_CTL_01')
        self.assertIn('High', result['nguyên nhân quyết định'])

    def test_process_optimal_normal(self):
        # Test Rule R_CTL_00: Optimal moisture & Normal temp -> Zero flow, Off power
        data = {
            'soil_moisture': 67,     # Optimal peak
            'temperature': 25,       # Normal peak
            'solar_radiation': 10000,
            'tank_level': 100,       
            'ph': 7.0,
            'pump_power': 50,
            'pump_flow': 50
        }
        result = self.fuzzy_agent.process(data)
        
        self.assertEqual(result['mã_luật'], 'R_CTL_00')
        self.assertEqual(result['loại_hành_động'], 'Điều khiển')

    def test_anomaly_pump_overload(self):
        # Test Rule R_ANO_05: Pump Overload -> Anomaly
        data = {
            'pump_power': 90, # Overload peak
        }
        result = self.fuzzy_agent.process(data)
        
        self.assertEqual(result['mã_luật'], 'R_ANO_05')
        self.assertEqual(result['loại_hành_động'], 'Bất thường')
        self.assertIn('Zero', result['quyết định'])

    def test_process_missing_data(self):
        # Test when input data is missing (fallback to safe defaults)
        data = {}
        result = self.fuzzy_agent.process(data)
        self.assertIn('fuzzy_outputs', result)
        self.assertIsNotNone(result['fuzzy_outputs']['flow_rate'])

if __name__ == '__main__':
    unittest.main()
