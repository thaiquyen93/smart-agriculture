import json
import os

class FuzzyDBService:
    def __init__(self, db_path="app/fuzzy/rules.json"):
        self.db_path = db_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def get_all_rules(self):
        """Đọc danh sách các luật mờ từ file JSON."""
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading fuzzy rules: {e}")
            return []

    def add_rule(self, rule_data):
        """Thêm một luật mới vào file JSON."""
        rules = self.get_all_rules()
        rules.append(rule_data)
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving fuzzy rules: {e}")
            return False
