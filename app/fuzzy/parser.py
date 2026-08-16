import re
from skfuzzy import control as ctrl

class FuzzyRuleParser:
    """
    Trình phân tích (Parser) để dịch các chuỗi văn bản tự nhiên thành luật logic mờ (skfuzzy Rules).
    Ví dụ: IF soil_moisture == 'Very Dry' OR temperature == 'Hot' THEN flow_rate = 'High'
    """
    def __init__(self, agent):
        # Lưu tham chiếu tới FuzzyAgent để truy xuất các biến Antecedent/Consequent
        self.agent = agent

    def parse_rule(self, rule_str):
        raw_rule = rule_str
        rule_id = "UNKNOWN"
        if ": IF " in rule_str:
            rule_id, rule_str = rule_str.split(": IF ", 1)
            rule_str = "IF " + rule_str
            
        if not rule_str.startswith("IF "):
            return None
        
        parts = rule_str[3:].split(" THEN ")
        if len(parts) != 2:
            return None
            
        ant_str, cons_str = parts[0], parts[1]
        
        # Parse antecedent
        ant_expr = self._parse_antecedent(ant_str)
        if ant_expr is None:
            return None
            
        # Parse consequent
        cons_list = self._parse_consequent(cons_str)
        if not cons_list:
            return None
            
        if len(cons_list) == 1:
            cons_list = cons_list[0]
            
        # Dùng chuỗi gốc làm label
        return ctrl.Rule(ant_expr, cons_list, label=raw_rule)

    def _parse_antecedent(self, ant_str):
        # Pattern tìm các cụm như: soil_moisture == 'Very Dry' hoặc temperature = "Hot"
        pattern = r'([a-zA-Z_0-9]+)\s*(?:==|IS|=)\s*[\'"]([^\'"]+)[\'"]'
        
        expr_dict = {}
        cond_idx = 0
        
        def replacer(match):
            nonlocal cond_idx
            var_name = match.group(1)
            term_name = match.group(2)
            
            ant_var = getattr(self.agent, var_name, None)
            if ant_var is not None:
                term = ant_var[term_name]
                cond_key = f"cond_{cond_idx}"
                expr_dict[cond_key] = term
                cond_idx += 1
                return cond_key
            return "False" # Fallback if variable is missing
            
        # Thay thế các biểu thức so sánh bằng các khóa biến (cond_0, cond_1...)
        parsed_str = re.sub(pattern, replacer, ant_str)
        
        # Chuyển đổi toán tử sang dạng bitwise của Python (skfuzzy dùng | và &)
        parsed_str = parsed_str.replace(" OR ", " | ").replace(" AND ", " & ")
        
        try:
            # Eval an toàn với context chỉ chứa các biến điều kiện
            return eval(parsed_str, {"__builtins__": None}, expr_dict)
        except Exception as e:
            print(f"Failed to parse antecedent: {ant_str} -> {e}")
            return None

    def _parse_consequent(self, cons_str):
        # Pattern giống Antecedent
        pattern = r'([a-zA-Z_0-9]+)\s*(?:==|IS|=)\s*[\'"]([^\'"]+)[\'"]'
        
        # Hỗ trợ cả dấu phẩy và chữ AND trong vế THEN
        cons_str = cons_str.replace(" AND ", ",")
        parts = [p.strip() for p in cons_str.split(",")]
        
        cons_list = []
        for part in parts:
            match = re.search(pattern, part)
            if match:
                var_name = match.group(1)
                term_name = match.group(2)
                cons_var = getattr(self.agent, var_name, None)
                if cons_var is not None:
                    cons_list.append(cons_var[term_name])
                    
        return cons_list
