import numpy as np
import skfuzzy as fuzz
import re
from skfuzzy import control as ctrl
from typing import Dict, Any
from app.core.base_agent import BaseAgent
from app.fuzzy.db import FuzzyDBService
from app.fuzzy.parser import FuzzyRuleParser

class FuzzyVal:
    """Class hỗ trợ tính toán AND/OR mờ cho các float thông qua toán tử bitwise của Python."""
    def __init__(self, val):
        self.val = val
    def __or__(self, other):
        return FuzzyVal(max(self.val, other.val))
    def __and__(self, other):
        return FuzzyVal(min(self.val, other.val))

class FuzzyAgent(BaseAgent):
    """
    Agent thực hiện suy diễn mờ (Fuzzy Inference) dựa trên scikit-fuzzy.
    Hỗ trợ nạp luật động từ chuỗi Text tự nhiên thông qua Parser.
    """
    def __init__(self):
        super().__init__(name="FuzzyAgent")
        self._setup_fuzzy_system()

    def _setup_fuzzy_system(self):
        # 1. Khai báo các biến đầu vào
        self.soil_moisture = ctrl.Antecedent(np.arange(0, 101, 1), 'soil_moisture')
        self.temperature = ctrl.Antecedent(np.arange(0, 51, 1), 'temperature')
        self.solar_radiation = ctrl.Antecedent(np.arange(0, 100001, 100), 'solar_radiation')
        self.tank_level = ctrl.Antecedent(np.arange(0, 101, 1), 'tank_level')
        self.ph = ctrl.Antecedent(np.arange(0, 14.1, 0.1), 'ph')
        self.humidity = ctrl.Antecedent(np.arange(0, 101, 1), 'humidity')
        self.pump_power = ctrl.Antecedent(np.arange(0, 101, 1), 'pump_power')
        self.pump_flow = ctrl.Antecedent(np.arange(0, 101, 1), 'pump_flow')

        # 2. Khai báo các biến đầu ra
        self.flow_rate = ctrl.Consequent(np.arange(0, 101, 1), 'flow_rate')
        self.power = ctrl.Consequent(np.arange(0, 101, 1), 'power')

        # 3. Định nghĩa các tập mờ
        self.soil_moisture.automf(names=['Very Dry', 'Dry', 'Optimal', 'Wet'])
        self.temperature.automf(names=['Cool', 'Normal', 'Hot'])
        self.solar_radiation.automf(names=['Low', 'Medium', 'High'])
        self.tank_level.automf(names=['Low', 'Medium', 'High'])
        self.ph.automf(names=['Low Acidic', 'Optimal', 'High Alkaline'])
        self.humidity.automf(names=['Low', 'Medium', 'High'])
        self.pump_power.automf(names=['Off', 'Idle', 'Nominal', 'Overload'])
        self.pump_flow.automf(names=['Zero', 'Low', 'Normal', 'High'])

        self.flow_rate.automf(names=['Zero', 'Low', 'Normal', 'High'])
        self.power.automf(names=['Off', 'Idle', 'Nominal', 'Overload'])

        # 4. Tải luật từ DB
        self.db_service = FuzzyDBService()
        self.raw_rules = self.db_service.get_all_rules()
        self.rule_parser = FuzzyRuleParser(self)
        
        skfuzzy_rules = []
        for r_str in self.raw_rules:
            r = self.rule_parser.parse_rule(r_str)
            if r is not None:
                skfuzzy_rules.append(r)

        # 5. Khởi tạo Control System
        if skfuzzy_rules:
            self.irrigation_ctrl = ctrl.ControlSystem(skfuzzy_rules)
            self.irrigation_sim = ctrl.ControlSystemSimulation(self.irrigation_ctrl)
        else:
            self.irrigation_ctrl = None
            self.irrigation_sim = None

    def _get_membership(self, antecedent, term_name, val):
        term = antecedent[term_name]
        return fuzz.interp_membership(antecedent.universe, term.mf, val)

    def _evaluate_rule_activation(self, rule_str, val_map):
        """Tự động tính độ kích hoạt (activation) của một luật văn bản."""
        if ": IF " in rule_str:
            _, rule_str = rule_str.split(": IF ", 1)
            rule_str = "IF " + rule_str
            
        if not rule_str.startswith("IF "):
            return 0.0
        
        parts = rule_str[3:].split(" THEN ")
        ant_str = parts[0]
        
        pattern = r'([a-zA-Z_0-9]+)\s*(?:==|IS|=)\s*[\'"]([^\'"]+)[\'"]'
        expr_dict = {}
        cond_idx = 0
        
        def replacer(match):
            nonlocal cond_idx
            var_name = match.group(1)
            term_name = match.group(2)
            
            ant_var = getattr(self, var_name, None)
            if ant_var is not None:
                crisp_val = val_map.get(var_name, 0)
                activation = self._get_membership(ant_var, term_name, crisp_val)
                cond_key = f"cond_{cond_idx}"
                expr_dict[cond_key] = FuzzyVal(activation)
                cond_idx += 1
                return cond_key
            return "FuzzyVal(0.0)"
            
        parsed_str = re.sub(pattern, replacer, ant_str)
        parsed_str = parsed_str.replace(" OR ", " | ").replace(" AND ", " & ")
        
        try:
            result = eval(parsed_str, {"FuzzyVal": FuzzyVal, "__builtins__": None}, expr_dict)
            return result.val if isinstance(result, FuzzyVal) else 0.0
        except Exception:
            return 0.0

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("Đang chạy logic suy diễn mờ IoT (Rule Parser)")
        
        if self.irrigation_sim is None:
            data['quyết định'] = "Lỗi xử lý mờ"
            data['nguyên nhân quyết định'] = "Không có luật nào trong DB để thực thi"
            return data
            
        try:
            val_soil = data.get('soil_moisture', 50)
            val_temp = data.get('temperature', 25)
            val_solar = data.get('solar_radiation', 10000)
            val_tank = data.get('tank_level', 80)
            val_ph = data.get('ph', 7.0)
            val_hum = data.get('humidity', 60)
            val_pump_pow = data.get('pump_power', 0)
            val_pump_flow = data.get('pump_flow', 0)
            
            # Chỉ truyền vào skfuzzy nếu luật có đòi hỏi (skfuzzy có thể quăng ValueError nếu input không dùng trong rule nào)
            try: self.irrigation_sim.input['soil_moisture'] = val_soil
            except ValueError: pass
            try: self.irrigation_sim.input['temperature'] = val_temp
            except ValueError: pass
            try: self.irrigation_sim.input['solar_radiation'] = val_solar
            except ValueError: pass
            try: self.irrigation_sim.input['tank_level'] = val_tank
            except ValueError: pass
            try: self.irrigation_sim.input['ph'] = val_ph
            except ValueError: pass
            try: self.irrigation_sim.input['humidity'] = val_hum
            except ValueError: pass
            try: self.irrigation_sim.input['pump_power'] = val_pump_pow
            except ValueError: pass
            try: self.irrigation_sim.input['pump_flow'] = val_pump_flow
            except ValueError: pass

            try:
                self.irrigation_sim.compute()
                out_flow = self.irrigation_sim.output.get('flow_rate', 0)
                out_power = self.irrigation_sim.output.get('power', 0)
            except Exception:
                out_flow = 0
                out_power = 0
            
            # Tính toán lại độ kích hoạt trực tiếp từ file văn bản
            best_activation = 0.0
            best_reason = "(Không có luật nào kích hoạt rõ ràng)"
            best_rule_id = "UNKNOWN"
            
            val_map = {
                'soil_moisture': val_soil,
                'temperature': val_temp,
                'solar_radiation': val_solar,
                'tank_level': val_tank,
                'ph': val_ph,
                'humidity': val_hum,
                'pump_power': val_pump_pow,
                'pump_flow': val_pump_flow
            }
            
            for rule_str in self.raw_rules:
                r_id = "UNKNOWN"
                r_text = rule_str
                if ": IF " in rule_str:
                    r_id, r_text = rule_str.split(": IF ", 1)
                    r_text = "IF " + r_text
                    
                rule_act = self._evaluate_rule_activation(rule_str, val_map)
                if rule_act > best_activation:
                    best_activation = rule_act
                    best_reason = r_text
                    best_rule_id = r_id
            
            # Xác định loại hành động (Bất thường vs Điều khiển)
            is_anomaly = best_rule_id.startswith("R_ANO")
            action_text = ""
            
            if best_reason and " THEN " in best_reason:
                action_text = best_reason.split(" THEN ")[1].strip()
            
            if is_anomaly:
                decision = f"Bất thường: {action_text} (Lưu lượng {round(out_flow, 2)} L/min, Công suất {round(out_power, 2)}%)"
            else:
                if action_text:
                    decision = f"Điều khiển máy bơm: {action_text} (Lưu lượng {round(out_flow, 2)} L/min, Công suất {round(out_power, 2)}%)"
                else:
                    decision = f"Điều khiển máy bơm: Lưu lượng {round(out_flow, 2)} L/min, Công suất {round(out_power, 2)}%"
            
            result = data.copy()
            result['quyết định'] = decision
            result['mã_luật'] = best_rule_id
            result['loại_hành_động'] = "Bất thường" if is_anomaly else "Điều khiển"
            result['nguyên nhân quyết định'] = best_reason
            result['fuzzy_outputs'] = {
                'flow_rate': round(out_flow, 2),
                'power': round(out_power, 2)
            }
            
            return result
        except Exception as e:
            self.logger.error(f"Lỗi khi thực hiện Fuzzy Inference: {e}")
            data['quyết định'] = "Lỗi xử lý mờ"
            data['nguyên nhân quyết định'] = str(e)
            return data
