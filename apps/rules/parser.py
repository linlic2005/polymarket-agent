"""
Rules 解析器。

负责解析规则文本，提取核心信息：
1. 结算源 (resolution source)
2. 截止时间 (end date)
3. 边缘条件 (edge cases)
4. 生成规则清晰度提示 (rule_clarity_hint)
"""

from __future__ import annotations

import re
from typing import Any


class RulesParser:
    """提取 Polymarket 规则文本的关键信息的解析器。"""

    def __init__(self, rule_text: str | None) -> None:
        self.rule_text = rule_text or ""

    def extract_resolution_source(self) -> str | None:
        """
        提取结算判定源。
        规则：找 "Resolution Source:", "resolution source is" 等关键词。
        """
        match = re.search(r'(?i)resolution source[:\s]+(.*?(?:\.|\n))', self.rule_text)
        if match:
            return match.group(1).strip()
        # Fallback simple search
        if "CNN" in self.rule_text or "Fox News" in self.rule_text:
            return "Major News Organziations"
        return None

    def extract_end_date(self) -> str | None:
        """
        提取截止日期/时间。
        规则：找 "by [Date]" or "Expires on [Date]" 格式
        """
        match = re.search(r'(?i)(?:by|on|before)\s+((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[^\.]*?(?:20\d\d))', self.rule_text)
        if match:
            return match.group(1).strip()
        return None

    def extract_edge_cases(self) -> list[str]:
        """
        提取边缘条件。
        规则：寻找 "If X happens, then... " 或 "Exceptions:" 
        """
        cases = []
        for line in self.rule_text.split('\n'):
            if re.search(r'(?i)^(if .*? then|otherwise|exception:)', line.strip()):
                cases.append(line.strip())
        return cases

    def evaluate_clarity(self) -> str:
        """
        评估规则清晰度。
        """
        if not self.rule_text:
            return "unclear"
        
        has_source = bool(self.extract_resolution_source())
        has_date = bool(self.extract_end_date())
        
        if has_source and has_date:
            return "very_clear"
        if has_source or has_date:
            return "clear"
        return "ambiguous"

    def parse_all(self) -> dict[str, Any]:
        """执行全体解析并返回字典。"""
        return {
            "resolution_source": self.extract_resolution_source(),
            "end_date": self.extract_end_date(),
            "edge_cases": self.extract_edge_cases(),
            "rule_clarity_hint": self.evaluate_clarity()
        }
