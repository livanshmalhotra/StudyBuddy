"""
core/answer.py — LLM Answer Synthesis via Ollama (Gemma) with Citation Prompting
"""
from __future__ import annotations

import logging
from typing import Optional
import httpx

from core.config import settings
from core.search import SearchResult
from core.cache import cache_answer

logger = logging.getLogger(__name__)


def synthesize_answer(query: str, chunks: list[SearchResult], auto_cache: bool = True) -> Optional[str]:
    """
    Synthesizes a direct answer citing chunk sources ([filename, p.X]) using Ollama (Gemma).
    """
    if not chunks:
        return None

    # Gather top 3 passages for context with citation tags
    context_passages = []
    for c in chunks[:3]:
        page_str = f", p.{c.page + 1}" if c.page is not None else ""
        source_label = f"[{c.filename}{page_str}]"
        context_passages.append(f"Source {source_label}:\n{c.text}")

    context_text = "\n\n".join(context_passages)

    prompt = f"""Extract key answer details from the document context below for the user's question.
Format your answer as 1-3 short, bulleted pointer statements (using •) so it is easy for a student to read.
Cite the source tag (e.g. [filename, p.X]) for key facts. Do not write introductory preamble.
If the answer is not in the context, output: Answer not found.

Context:
{context_text}

Question: {query}
Key Pointers Answer:"""

    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": settings.LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 80,
            },
        }
        with httpx.Client() as client:
            resp = client.post(url, json=payload, timeout=60.0)
            if resp.status_code == 200:
                raw_ans = resp.json().get("response", "").strip()
                if raw_ans and not raw_ans.lower().startswith("answer not found"):
                    if auto_cache:
                        cache_answer(query, raw_ans)
                    return raw_ans
    except Exception as exc:
        logger.warning(f"Ollama LLM answer synthesis failed/timed out: {exc}")
        return None

    return None
