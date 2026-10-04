"""
core/agent.py — Agent Router with Thread Memory
Routes user intent to search_notes, answer_question, make_quiz, or weak_topics.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List
from core.tools import search_notes, answer_question, make_quiz, weak_topics

logger = logging.getLogger(__name__)

# Simple in-memory thread store
THREAD_MEMORY: Dict[str, List[Dict[str, str]]] = {}


def agent_chat(thread_id: str, message: str) -> Dict[str, Any]:
    """
    Main agent entry point. Manages thread memory and routes intent to tools.
    """
    if thread_id not in THREAD_MEMORY:
        THREAD_MEMORY[thread_id] = []

    history = THREAD_MEMORY[thread_id]
    history.append({"role": "user", "content": message})

    msg_lower = message.lower()

    # Intent routing
    if "quiz" in msg_lower or "test" in msg_lower or "practice" in msg_lower:
        result = make_quiz()
        response_text = f"Prepared quiz on {result['topic']} with {result['question_count']} questions."
        tool_used = "make_quiz"

    elif "weak" in msg_lower or "improve" in msg_lower or "struggling" in msg_lower:
        result = weak_topics()
        topics_str = ", ".join(t["topic"] for t in result["weak_topics"])
        response_text = f"Your top weak areas: {topics_str}."
        tool_used = "weak_topics"

    elif "find" in msg_lower or "search" in msg_lower or "where" in msg_lower:
        result = search_notes(message)
        response_text = f"Found {result['count']} relevant notes."
        tool_used = "search_notes"

    else:
        result = answer_question(message)
        response_text = result.get("answer", "No answer found.")
        tool_used = "answer_question"

    history.append({"role": "assistant", "content": response_text, "tool": tool_used})

    return {
        "thread_id": thread_id,
        "tool_used": tool_used,
        "response": response_text,
        "details": result,
    }
