"""
core/quiz.py — Question Generation, Caching, Retrieval & Attempt Logging
"""
from __future__ import annotations

import json
import logging
from typing import List, Dict, Any, Optional
import httpx

from core.config import settings
from core.db import Session, QuestionModel, AttemptModel, Chunk

logger = logging.getLogger(__name__)


def generate_question_from_chunk(chunk_id: int, chunk_text: str, topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Calls Gemma LLM via Ollama to generate an MCQ question grounded in the chunk text.
    """
    prompt = f"""Based ONLY on the text below, generate 1 multiple-choice question (MCQ) with 4 options (A, B, C, D) and specify the correct option letter.

Text:
{chunk_text[:1000]}

Respond ONLY in valid JSON with format:
{{
  "type": "mcq",
  "stem": "Question text here?",
  "options": {{ "A": "...", "B": "...", "C": "...", "D": "..." }},
  "answer": "A",
  "difficulty": "medium"
}}"""

    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": settings.LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 200},
        }
        with httpx.Client() as client:
            resp = client.post(url, json=payload, timeout=30.0)
            if resp.status_code == 200:
                raw = resp.json().get("response", "").strip()
                # Extract JSON block
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start != -1 and end != -1:
                    data = json.loads(raw[start:end])
                    data["chunk_id"] = chunk_id
                    data["topic"] = topic or "General Notes"
                    return data
    except Exception as exc:
        logger.warning(f"Failed to generate question with Gemma: {exc}")

    return None


def get_or_create_quiz(topic: Optional[str] = None, count: int = 5) -> List[Dict[str, Any]]:
    """
    Fetches cached questions for topic/docs or generates new ones from chunks.
    """
    with Session() as session:
        query = session.query(QuestionModel)
        if topic:
            query = query.filter(QuestionModel.topic == topic)
        questions = query.limit(count).all()

        if len(questions) >= count:
            return [
                {
                    "id": q.id,
                    "chunk_id": q.chunk_id,
                    "type": q.type,
                    "stem": q.stem,
                    "options": q.options if isinstance(q.options, dict) else (json.loads(q.options) if q.options else {}),
                    "answer": q.answer,
                    "difficulty": q.difficulty,
                    "topic": q.topic,
                }
                for q in questions
            ]

        # If cached questions count is thin, generate from ready chunks
        chunks = session.query(Chunk).limit(count * 2).all()
        created_questions = []

        for c in chunks:
            if len(created_questions) >= count:
                break
            q_data = generate_question_from_chunk(c.id, c.text, topic=topic or c.heading)
            if q_data:
                q_obj = QuestionModel(
                    chunk_id=c.id,
                    type=q_data.get("type", "mcq"),
                    stem=q_data["stem"],
                    options=q_data.get("options", {}),
                    answer=q_data["answer"],
                    difficulty=q_data.get("difficulty", "medium"),
                    topic=q_data.get("topic", "General Notes"),
                )
                session.add(q_obj)
                session.flush()
                q_data["id"] = q_obj.id
                created_questions.append(q_data)

        session.commit()

        if created_questions:
            return created_questions

        # Fallback question if generation unavailable
        return [
            {
                "id": 1,
                "chunk_id": 1,
                "type": "mcq",
                "stem": "What is the primary definition of Environment in the study notes?",
                "options": {
                    "A": "Everything that surrounds or affects an organism during its lifetime.",
                    "B": "Only the physical buildings and urban structures.",
                    "C": "Deep ocean water below 500 meters.",
                    "D": "Inorganic chemicals only.",
                },
                "answer": "A",
                "difficulty": "easy",
                "topic": "Environmental Studies",
            }
        ]


def record_attempt(question_id: int, topic: str, correct: bool, seconds_taken: int = 10) -> Dict[str, Any]:
    """
    Logs quiz attempt into attempts table for TabPFN analytics.
    """
    with Session() as session:
        attempt = AttemptModel(
            question_id=question_id,
            topic=topic,
            correct=bool(correct),
            seconds_taken=seconds_taken,
            days_since_last_seen=0,
        )
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        return {
            "attempt_id": attempt.id,
            "question_id": question_id,
            "correct": correct,
            "status": "recorded",
        }
