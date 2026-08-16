import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from typing import Dict, Any
from app.agents.base import BaseAgent

class FuzzyAgent(BaseAgent):
    """
    Agent thực hiện suy diễn mờ (Fuzzy Inference) dựa trên scikit-fuzzy.
    """
    def __init__(self):
        super().__init__(name="FuzzyAgent")
        self._setup_fuzzy_system()

    def _setup_fuzzy_system(self):
        # Antecedent/Consequent objects hold universe variables and membership functions
        self.quality = ctrl.Antecedent(np.arange(0, 11, 1), 'quality')
        self.service = ctrl.Antecedent(np.arange(0, 11, 1), 'service')
        self.tip = ctrl.Consequent(np.arange(0, 26, 1), 'tip')

        # Auto-membership function population
        self.quality.automf(3)
        self.service.automf(3)

        # Custom membership functions
        self.tip['low'] = fuzz.trimf(self.tip.universe, [0, 0, 13])
        self.tip['medium'] = fuzz.trimf(self.tip.universe, [0, 13, 25])
        self.tip['high'] = fuzz.trimf(self.tip.universe, [13, 25, 25])

        rule1 = ctrl.Rule(self.quality['poor'] | self.service['poor'], self.tip['low'])
        rule2 = ctrl.Rule(self.service['average'], self.tip['medium'])
        rule3 = ctrl.Rule(self.service['good'] | self.quality['good'], self.tip['high'])

        self.tipping_ctrl = ctrl.ControlSystem([rule1, rule2, rule3])
        self.tipping_sim = ctrl.ControlSystemSimulation(self.tipping_ctrl)

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sử dụng Scikit-Fuzzy để suy diễn logic mờ, dựa trên dữ liệu hiện tại và tương lai.
        """
        self.logger.info("Đang chạy logic suy diễn mờ")
        try:
            # Lấy data gốc, nếu có tương lai thì ưu tiên kết hợp
            future_state = data.get('future_state', {})
            val_quality = future_state.get('predicted_quality_t1', data.get('quality', 5))
            val_service = future_state.get('predicted_service_t1', data.get('service', 5))
            
            self.tipping_sim.input['quality'] = val_quality
            self.tipping_sim.input['service'] = val_service

            # Crunch the numbers
            self.tipping_sim.compute()

            tip_result = self.tipping_sim.output['tip']
            
            # Khởi tạo quyết định và nguyên nhân
            decision = f"Gợi ý mức tip là {round(tip_result, 2)}%"
            reason = f"Chất lượng dự kiến là {val_quality} và Dịch vụ dự kiến là {val_service}."
            
            if tip_result < 10:
                reason += " Mức tip thấp do chất lượng hoặc dịch vụ quá tệ."
            elif tip_result > 20:
                reason += " Mức tip cao do dịch vụ và chất lượng xuất sắc."
                
            result = data.copy()
            result['quyết định'] = decision
            result['nguyên nhân quyết định'] = reason
            
            return result
        except Exception as e:
            self.logger.error(f"Lỗi khi thực hiện Fuzzy Inference: {e}")
            data['quyết định'] = "Lỗi xử lý mờ"
            data['nguyên nhân quyết định'] = str(e)
            return data
