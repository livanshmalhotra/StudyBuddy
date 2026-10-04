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
    prompt = f"""You are an exam question creator. Read the study note passage below and write ONE specific multiple-choice question (MCQ) testing key concepts in it.

Passage:
{chunk_text[:800]}

Write a specific, meaningful question in the "stem" field, 4 clear options (A, B, C, D), and the correct option letter.

Respond ONLY with valid JSON matching this exact format:
{{
  "type": "mcq",
  "stem": "Which data structure follows the Last-In First-Out (LIFO) principle?",
  "options": {{
    "A": "Stack",
    "B": "Queue",
    "C": "Linked List",
    "D": "Binary Tree"
  }},
  "answer": "A",
  "difficulty": "medium"
}}"""

    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": settings.LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 350},
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
                    stem = str(data.get("stem", "")).strip()
                    # Filter out placeholder or bogus questions
                    if not stem or "question text" in stem.lower() or len(stem) < 8:
                        return None
                    data["chunk_id"] = chunk_id
                    data["topic"] = topic or "General Notes"
                    return data
    except Exception as exc:
        logger.warning(f"Failed to generate question with Gemma: {exc}")

    return None


def get_or_create_quiz(topic: Optional[str] = None, count: int = 5) -> List[Dict[str, Any]]:
    """
    Fetches cached questions for topic/docs or generates new ones from chunks.
    Randomizes selection and deduplicates stems so quizzes feel fresh.
    """
    from sqlalchemy.sql.expression import func

    with Session() as session:
        # Purge any legacy placeholder questions if they exist
        session.execute(
            QuestionModel.__table__.delete().where(
                QuestionModel.stem.ilike("%question text%")
            )
        )
        session.commit()

        # Fetch cached questions — randomized so each quiz session is different
        query = session.query(QuestionModel).filter(
            ~QuestionModel.stem.ilike("%question text%")
        )
        if topic:
            query = query.filter(QuestionModel.topic == topic)

        total_cached = query.count()

        if total_cached >= count:
            # Randomly pick `count` questions from the full pool
            questions = query.order_by(func.random()).limit(count).all()
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

        # Not enough cached — generate from chunks that DON'T already have questions
        existing_chunk_ids = {
            row[0] for row in session.query(QuestionModel.chunk_id).all()
        }

        # Get chunks, preferring ones without questions, randomized
        chunks = (
            session.query(Chunk)
            .filter(~Chunk.id.in_(existing_chunk_ids) if existing_chunk_ids else True)
            .order_by(func.random())
            .limit(count * 3)
            .all()
        )

        # Fallback: if all chunks already have questions, just pick random chunks
        if not chunks:
            chunks = session.query(Chunk).order_by(func.random()).limit(count * 3).all()

        created_questions = []
        seen_stems = set()

        for c in chunks:
            if len(created_questions) >= count:
                break
            q_data = generate_question_from_chunk(c.id, c.text, topic=topic or c.heading)
            if not q_data:
                continue

            # Deduplicate: skip if stem is too similar to one we already have
            stem_lower = q_data["stem"].lower().strip()
            if stem_lower in seen_stems:
                continue
            seen_stems.add(stem_lower)

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
                "stem": "What is a key advantage of binary search over linear search?",
                "options": {
                    "A": "O(log n) time complexity on sorted arrays.",
                    "B": "Works on unsorted linked lists directly.",
                    "C": "Requires O(n^2) auxiliary memory space.",
                    "D": "Executes without array index bounds.",
                },
                "answer": "A",
                "difficulty": "easy",
                "topic": "Data Structures & Algorithms",
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
