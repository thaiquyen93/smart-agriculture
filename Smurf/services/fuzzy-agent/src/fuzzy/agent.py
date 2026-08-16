import numpy as np
import skfuzzy as fuzz
import re
from skfuzzy import control as ctrl
from typing import Dict, Any
from src.core.base_agent import BaseAgent
from src.fuzzy.db import FuzzyDBService
from src.fuzzy.parser import FuzzyRuleParser

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
        self.humidity = ctrl.Antecedent(np.arange(0, 101, 1), 'humidity')
        self.flow_rate = ctrl.Antecedent(np.arange(0, 101, 1), 'flow_rate')
        self.power = ctrl.Antecedent(np.arange(0, 101, 1), 'power')
        self.ph = ctrl.Antecedent(np.arange(0, 14.1, 0.1), 'ph')
        self.level = ctrl.Antecedent(np.arange(0, 101, 1), 'level')
        self.lux = ctrl.Antecedent(np.arange(0, 100001, 100), 'lux')

        # 2. Khai báo các biến đầu ra
        self.pump_flow = ctrl.Consequent(np.arange(0, 101, 1), 'pump_flow')
        self.pump_power = ctrl.Consequent(np.arange(0, 101, 1), 'pump_power')

        # 3. Định nghĩa các tập mờ
        self.soil_moisture.automf(names=['Very Dry', 'Dry', 'Optimal', 'Wet'])
        self.temperature.automf(names=['Cool', 'Normal', 'Hot'])
        self.humidity.automf(names=['Low', 'Medium', 'High'])
        self.flow_rate.automf(names=['Zero', 'Low', 'Normal', 'High'])
        self.power.automf(names=['Off', 'Idle', 'Nominal', 'Overload'])
        self.ph.automf(names=['Low Acidic', 'Optimal', 'High Alkaline'])
        self.level.automf(names=['Low', 'Medium', 'High'])
        self.lux.automf(names=['Low', 'Medium', 'High'])

        self.pump_flow.automf(names=['Zero', 'Low', 'Normal', 'High'])
        self.pump_power.automf(names=['Off', 'Idle', 'Nominal', 'Overload'])

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
            data['decision'] = "Fuzzy Processing Error"
            data['decision_reason'] = "No rules found in DB to execute"
            return data
            
        try:
            val_soil = data.get('soil_moisture', 50)
            val_temp = data.get('temperature', 25)
            val_hum = data.get('humidity', 60)
            val_flow = data.get('flow_rate', 0)
            val_pow = data.get('power', 0)
            val_ph = data.get('ph', 7.0)
            val_level = data.get('level', 80)
            val_lux = data.get('lux', 10000)
            
            # Chỉ truyền vào skfuzzy nếu luật có đòi hỏi (skfuzzy có thể quăng ValueError nếu input không dùng trong rule nào)
            try: self.irrigation_sim.input['soil_moisture'] = val_soil
            except ValueError: pass
            try: self.irrigation_sim.input['temperature'] = val_temp
            except ValueError: pass
            try: self.irrigation_sim.input['humidity'] = val_hum
            except ValueError: pass
            try: self.irrigation_sim.input['flow_rate'] = val_flow
            except ValueError: pass
            try: self.irrigation_sim.input['power'] = val_pow
            except ValueError: pass
            try: self.irrigation_sim.input['ph'] = val_ph
            except ValueError: pass
            try: self.irrigation_sim.input['level'] = val_level
            except ValueError: pass
            try: self.irrigation_sim.input['lux'] = val_lux
            except ValueError: pass

            try:
                self.irrigation_sim.compute()
                out_pump_flow = self.irrigation_sim.output.get('pump_flow', 0)
                out_pump_power = self.irrigation_sim.output.get('pump_power', 0)
            except Exception:
                out_pump_flow = 0
                out_pump_power = 0
            
            best_reason = "(No rules explicitly activated)"
            best_rule_id = "UNKNOWN"
            
            val_map = {
                'soil_moisture': val_soil,
                'temperature': val_temp,
                'humidity': val_hum,
                'flow_rate': val_flow,
                'power': val_pow,
                'ph': val_ph,
                'level': val_level,
                'lux': val_lux
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
                decision = f"Anomaly: {action_text} (Pump Flow {round(out_pump_flow, 2)} L/min, Power {round(out_pump_power, 2)}%)"
            else:
                if action_text:
                    decision = f"Pump Control: {action_text} (Pump Flow {round(out_pump_flow, 2)} L/min, Power {round(out_pump_power, 2)}%)"
                else:
                    decision = f"Pump Control: Pump Flow {round(out_pump_flow, 2)} L/min, Power {round(out_pump_power, 2)}%"
            
            result = data.copy()
            result['decision'] = decision
            result['rule_id'] = best_rule_id
            result['action_type'] = "Anomaly" if is_anomaly else "Control"
            result['decision_reason'] = best_reason
            result['fuzzy_outputs'] = {
                'pump_flow': round(out_pump_flow, 2),
                'pump_power': round(out_pump_power, 2)
            }
            
            return result
        except Exception as e:
            self.logger.error(f"Error during Fuzzy Inference: {e}")
            data['decision'] = "Fuzzy Processing Error"
            data['decision_reason'] = str(e)
            return data
