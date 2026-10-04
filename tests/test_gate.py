"""
tests/test_gate.py — Unit tests for Confidence Gate and Answer Cache
"""
import pytest
from core.search import SearchResult
from core.gate import evaluate_gate, GateConfidence, HIGH_SCORE_THRESHOLD, MARGIN_THRESHOLD, MIN_RELEVANCE_THRESHOLD


def test_gate_no_match():
    # Empty results -> NO_MATCH
    assert evaluate_gate([]) == GateConfidence.NO_MATCH

    # Top score below minimum -> NO_MATCH
    low_res = SearchResult(
        chunk_id=1,
        text="Low score text",
        filename="doc.pdf",
        page=0,
        heading=None,
        fused_score=MIN_RELEVANCE_THRESHOLD - 0.001,
        vector_rank=10,
        text_rank=10,
        margin=0.0,
    )
    assert evaluate_gate([low_res]) == GateConfidence.NO_MATCH


def test_gate_high_confidence():
    # Top score >= 0.030 and margin >= 0.005 -> HIGH
    res1 = SearchResult(
        chunk_id=1,
        text="High score text 1",
        filename="doc.pdf",
        page=0,
        heading=None,
        fused_score=HIGH_SCORE_THRESHOLD + 0.005,
        vector_rank=1,
        text_rank=1,
        margin=MARGIN_THRESHOLD + 0.002,
    )
    res2 = SearchResult(
        chunk_id=2,
        text="High score text 2",
        filename="doc.pdf",
        page=0,
        heading=None,
        fused_score=HIGH_SCORE_THRESHOLD,
        vector_rank=2,
        text_rank=2,
        margin=0.0,
    )
    assert evaluate_gate([res1, res2]) == GateConfidence.HIGH


def test_gate_medium_low_confidence():
    # High score but small margin -> MEDIUM_LOW
    res1 = SearchResult(
        chunk_id=1,
        text="Med score text 1",
        filename="doc.pdf",
        page=0,
        heading=None,
        fused_score=HIGH_SCORE_THRESHOLD + 0.001,
        vector_rank=1,
        text_rank=1,
        margin=MARGIN_THRESHOLD - 0.002, # Small margin
    )
    res2 = SearchResult(
        chunk_id=2,
        text="Med score text 2",
        filename="doc.pdf",
        page=0,
        heading=None,
        fused_score=HIGH_SCORE_THRESHOLD,
        vector_rank=2,
        text_rank=2,
        margin=0.0,
    )
    assert evaluate_gate([res1, res2]) == GateConfidence.MEDIUM_LOW
