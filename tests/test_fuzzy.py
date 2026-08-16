import unittest
from app.agents.fuzzy_agent import FuzzyAgent

class TestFuzzyAgent(unittest.TestCase):
    def setUp(self):
        self.fuzzy_agent = FuzzyAgent()

    def test_process_valid_data(self):
        # Data với chất lượng và dịch vụ tốt
        data = {'quality': 9, 'service': 9}
        result = self.fuzzy_agent.process(data)
        
        self.assertIn('quyết định', result)
        self.assertIn('nguyên nhân quyết định', result)
        # Tip sẽ nằm trong khoảng khá cao (khoảng > 15)
        self.assertIn('tip', result['quyết định'].lower())

    def test_process_poor_data(self):
        # Data với chất lượng và dịch vụ kém
        data = {'quality': 1, 'service': 1}
        result = self.fuzzy_agent.process(data)
        
        self.assertIn('quyết định', result)
        self.assertIn('nguyên nhân quyết định', result)
        # Tip sẽ nằm trong khoảng khá thấp
        self.assertIn('thấp', result['nguyên nhân quyết định'])

if __name__ == '__main__':
    unittest.main()
