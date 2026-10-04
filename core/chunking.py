import os
import re
from dataclasses import dataclass
import tiktoken
from core.parsing import Page

CHUNK_MAX_TOKENS = int(os.environ.get("CHUNK_MAX_TOKENS", "400"))
CHUNK_OVERLAP_TOKENS = int(os.environ.get("CHUNK_OVERLAP_TOKENS", "50"))

@dataclass
class Chunk:
    doc_page: int | None
    heading: str | None
    text: str
    token_count: int

def chunk(pages: list[Page]) -> list[Chunk]:
    if not pages:
        return []

    encoder = tiktoken.get_encoding("cl100k_base")

    # Step 1: Extract sub-units from each page with doc_page and heading preserved.
    # Split text by sentence boundaries or line breaks.
    units: list[tuple[int | None, str | None, str, int]] = []

    for page in pages:
        raw_units = re.split(r'(?<=[.!?])\s+|\n+', page.text)
        for u_str in raw_units:
            text_str = u_str.strip()
            if not text_str:
                continue
            
            u_tokens = len(encoder.encode(text_str))
            if u_tokens <= CHUNK_MAX_TOKENS:
                units.append((page.page, page.heading, text_str, u_tokens))
            else:
                # Hard-split oversized text unit by word boundaries into sub-units <= CHUNK_MAX_TOKENS
                words = text_str.split()
                sub_words: list[str] = []
                sub_tokens = 0
                for word in words:
                    w_tokens = len(encoder.encode(word + " "))
                    if sub_tokens + w_tokens > CHUNK_MAX_TOKENS and sub_words:
                        sub_text = " ".join(sub_words)
                        units.append((page.page, page.heading, sub_text, sub_tokens))
                        sub_words = [word]
                        sub_tokens = w_tokens
                    else:
                        sub_words.append(word)
                        sub_tokens += w_tokens
                if sub_words:
                    sub_text = " ".join(sub_words)
                    units.append((page.page, page.heading, sub_text, sub_tokens))

    if not units:
        return []

    # Step 2: Accumulate units into chunks bounded by CHUNK_MAX_TOKENS
    results: list[Chunk] = []
    current_chunk_units: list[tuple[int | None, str | None, str, int]] = []
    current_chunk_tokens = 0

    for doc_page, heading, text_str, u_tokens in units:
        if current_chunk_tokens + u_tokens > CHUNK_MAX_TOKENS and current_chunk_units:
            chunk_text = " ".join(item[2] for item in current_chunk_units)
            results.append(Chunk(
                doc_page=current_chunk_units[0][0],
                heading=current_chunk_units[0][1],
                text=chunk_text,
                token_count=current_chunk_tokens
            ))

            # Backtrack overlap from previous chunk
            overlap_units: list[tuple[int | None, str | None, str, int]] = []
            overlap_tokens = 0
            for item in reversed(current_chunk_units):
                if overlap_tokens + item[3] <= CHUNK_OVERLAP_TOKENS:
                    overlap_units.insert(0, item)
                    overlap_tokens += item[3]
                else:
                    break

            current_chunk_units = overlap_units
            current_chunk_tokens = overlap_tokens

        current_chunk_units.append((doc_page, heading, text_str, u_tokens))
        current_chunk_tokens += u_tokens

    if current_chunk_units:
        chunk_text = " ".join(item[2] for item in current_chunk_units)
        results.append(Chunk(
            doc_page=current_chunk_units[0][0],
            heading=current_chunk_units[0][1],
            text=chunk_text,
            token_count=current_chunk_tokens
        ))

    return results

