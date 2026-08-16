import unittest
from app.agents.orchestrator import MultiAgentOrchestrator

class TestMultiAgentFlow(unittest.TestCase):
    def setUp(self):
        self.orchestrator = MultiAgentOrchestrator()

    def test_process_pipeline(self):
        input_data = {'quality': 1, 'service': 1} # Cố tình ép ra nguyên nhân 'thấp' -> LLM có thể trả FALSE
        result = self.orchestrator.process(input_data)
        
        # Kiểm tra xem có cấu trúc output đúng format không
        self.assertIn('quyết định', result)
        self.assertIn('nguyên nhân quyết định', result)
        self.assertIn('bất thường', result)
        self.assertIn('nguyên nhân bất thường', result)

if __name__ == '__main__':
    unittest.main()
