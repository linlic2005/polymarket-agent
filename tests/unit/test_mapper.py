"""
Mapper Module Tests.

Covering compute_mapping_score.
"""

import pytest

from apps.mapper.service import compute_mapping_score

def test_compute_mapping_score_exact_match():
    # Setup
    headline = "Bitcoin reaches new ATH"
    tags = ["Bitcoin", "BTC", "crypto"]
    pm_title = "Bitcoin reaches new ATH"
    
    score = compute_mapping_score(headline, tags, pm_title)
    # The heuristic gives points for headline and fractional points for tags match + base 0.1
    assert score > 0.75


def test_compute_mapping_score_partial_match():
    headline = "Donald Trump announced new tariff"
    tags = ["Donald Trump", "tariff"]
    pm_title = "Will Donald Trump announce tariff before Jan?"
    
    score = compute_mapping_score(headline, tags, pm_title)
    # Should get points from both title overlap and tags overlap
    # 0.1 (base) + some fraction
    assert score > 0.1
    assert score < 1.0


def test_compute_mapping_score_no_match():
    headline = "SpaceX launched completely new rocket"
    tags = ["SpaceX"]
    pm_title = "Will the fed cut interest rate by 50bps?"
    
    score = compute_mapping_score(headline, tags, pm_title)
    # No matches, so it gets just the base score
    assert score == 0.1
