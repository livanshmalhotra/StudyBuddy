"""
core/tools.py — Structured Agent Tools for Q&A, Quizzes, Weak Topics, and Grading
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Dict

from core.search import hybrid_search
from core.cache import get_cached_answer
from core.gate import evaluate_gate, GateConfidence
from core.answer import synthesize_answer

logger = logging.getLogger(__name__)


def search_notes(query: str, k: int = 5) -> Dict[str, Any]:
    """Tool: Searches user's study notes using hybrid vector + BM25 search."""
    results = hybrid_search(query, k=k)
    return {
        "count": len(results),
        "results": [
            {
                "chunk_id": r.chunk_id,
                "filename": r.filename,
                "page": r.page,
                "heading": r.heading,
                "score": r.fused_score,
                "snippet": r.text[:200],
            }
            for r in results
        ],
    }


def answer_question(query: str) -> Dict[str, Any]:
    """Tool: Full Q&A pipeline with answer cache, confidence gate, and Gemma LLM synthesis."""
    # 1. Cache lookup
    cached = get_cached_answer(query)
    if cached:
        return {
            "answer": cached["answer"],
            "gate_decision": "CACHE_HIT",
            "cache_hit": True,
            "llm_used": False,
        }

    # 2. Hybrid Retrieval
    results = hybrid_search(query, k=5)
    if not results:
        return {
            "answer": "Answer not found in your notes.",
            "gate_decision": "NO_MATCH",
            "cache_hit": False,
            "llm_used": False,
        }

    # 3. Gate decision
    gate_decision = evaluate_gate(results)

    if gate_decision == GateConfidence.HIGH:
        answer = f"Direct Passage [{results[0].filename}" + (f", p.{results[0].page + 1}" if results[0].page is not None else "") + "]:\n" + results[0].text
        return {
            "answer": answer,
            "gate_decision": "HIGH",
            "cache_hit": False,
            "llm_used": False,
        }

    elif gate_decision == GateConfidence.MEDIUM_LOW:
        ans = synthesize_answer(query, results, auto_cache=True)
        return {
            "answer": ans or "Answer not found in your notes.",
            "gate_decision": "MEDIUM_LOW",
            "cache_hit": False,
            "llm_used": bool(ans),
        }

    return {
        "answer": "Answer not found in your notes.",
        "gate_decision": "NO_MATCH",
        "cache_hit": False,
        "llm_used": False,
    }


def make_quiz(topic: Optional[str] = None, count: int = 5) -> Dict[str, Any]:
    """Tool Placeholder: Retrieves or generates practice questions for a topic."""
    from core.db import Session, Document
    with Session() as session:
        docs = session.query(Document).filter_by(status="ready").all()
        filenames = [d.filename for d in docs]

    return {
        "topic": topic or "General Notes",
        "question_count": count,
        "available_sources": filenames,
        "status": "ready",
    }


def weak_topics() -> Dict[str, Any]:
    """Tool Placeholder: Predicts weak study topics."""
    return {
        "weak_topics": [
            {"topic": "Environmental Studies", "priority": "high", "predicted_wrong_probability": 0.75},
            {"topic": "Ecosystem Structure", "priority": "medium", "predicted_wrong_probability": 0.45},
        ]
    }
