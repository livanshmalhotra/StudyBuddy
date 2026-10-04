"""
core/gate.py — Confidence Gate Decision Logic
Determines whether retrieval results are HIGH confidence (skip LLM),
MEDIUM_LOW confidence (route to Gemma LLM), or NO_MATCH (not in notes).
"""
from __future__ import annotations

from enum import Enum
from typing import Sequence
from core.search import SearchResult


class GateConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM_LOW = "MEDIUM_LOW"
    NO_MATCH = "NO_MATCH"


HIGH_SCORE_THRESHOLD = 0.030
MARGIN_THRESHOLD = 0.005
MIN_RELEVANCE_THRESHOLD = 0.005


def evaluate_gate(results: Sequence[SearchResult]) -> GateConfidence:
    """
    Evaluates confidence of hybrid retrieval results.
    - HIGH: top score >= 0.030 and margin >= 0.005 (Skip LLM, return direct passage).
    - MEDIUM_LOW: score >= 0.005 (Route to Gemma LLM for synthesis).
    - NO_MATCH: score < 0.005 or no results.
    """
    if not results:
        return GateConfidence.NO_MATCH

    top_score = results[0].fused_score
    margin = results[0].margin

    if top_score < MIN_RELEVANCE_THRESHOLD:
        return GateConfidence.NO_MATCH

    if top_score >= HIGH_SCORE_THRESHOLD and margin >= MARGIN_THRESHOLD:
        return GateConfidence.HIGH

    return GateConfidence.MEDIUM_LOW
