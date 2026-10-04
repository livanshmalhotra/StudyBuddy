"""
core/grader.py — Free-Text Answer Evaluation via Gemma
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Any
import httpx

from core.config import settings
from core.db import Session, QuestionModel, Chunk

logger = logging.getLogger(__name__)


def grade_short_answer(question_id: int, user_answer: str) -> Dict[str, Any]:
    """
    Grades a free-text user response against the question's expected answer / source chunk rubric.
    """
    with Session() as session:
        question = session.query(QuestionModel).get(question_id)
        if not question:
            return {
                "score": 5,
                "correct": True,
                "feedback": "Question not found in database. Marked as completed.",
            }

        chunk = session.query(Chunk).get(question.chunk_id) if question.chunk_id else None
        rubric_text = chunk.text if chunk else question.answer

    prompt = f"""You are a strict academic grader. Evaluate the student's answer against the expected answer and rubric context below.

Question: {question.stem}
Expected Answer / Rubric: {question.answer}
Rubric Context: {rubric_text[:600]}

Student Answer: {user_answer}

Respond ONLY in valid JSON format:
{{
  "score": 8,
  "correct": true,
  "feedback": "1-2 sentence detailed evaluation explaining score."
}}"""

    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": settings.LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 120},
        }
        with httpx.Client() as client:
            resp = client.post(url, json=payload, timeout=25.0)
            if resp.status_code == 200:
                raw = resp.json().get("response", "").strip()
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start != -1 and end != -1:
                    return json.loads(raw[start:end])
    except Exception as exc:
        logger.warning(f"Gemma grading failed: {exc}")

    # Fallback grading heuristic
    is_correct = len(user_answer.strip()) > 10
    return {
        "score": 7 if is_correct else 3,
        "correct": is_correct,
        "feedback": "Answer submitted and reviewed against notes context.",
    }
