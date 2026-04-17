"""
Rules Parser Tests.
"""

from apps.rules.parser import RulesParser

def test_rules_parser_full():
    rule_text = """
    Resolution Source: The official announcement by the Federal Reserve.
    This market will resolve to 'Yes' if the Fed cuts interest rates by 50 bps.
    If the announcement is delayed, then the market resolves NO.
    Expires on Dec 31, 2024.
    """
    
    parser = RulesParser(rule_text)
    
    # Check parse extraction methods
    assert parser.extract_resolution_source() == "The official announcement by the Federal Reserve."
    assert parser.extract_end_date() == "Dec 31, 2024"
    assert "If the announcement is delayed, then the market resolves NO." in parser.extract_edge_cases()
    
    # Check evaluate clarity
    assert parser.evaluate_clarity() == "very_clear"


def test_rules_parser_partial():
    rule_text = "The market resolves based on CNN reporting if Trump wins."
    parser = RulesParser(rule_text)
    
    assert parser.extract_resolution_source() == "Major News Organziations" # Matched CNN heuristic
    assert parser.extract_end_date() is None
    assert parser.extract_edge_cases() == []
    
    assert parser.evaluate_clarity() == "clear"


def test_rules_parser_unclear():
    rule_text = ""
    parser = RulesParser(rule_text)
    assert parser.evaluate_clarity() == "unclear"
