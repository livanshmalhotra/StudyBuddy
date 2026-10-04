"""
Quick runner: parse + chunk a file and print results.
Usage:  python run_parse.py uploads/room_request_letter.pdf
"""
import sys
from pathlib import Path

# ── resolve path ────────────────────────────────────────────────────────────
path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("uploads/room_request_letter.pdf")

from core.parsing import parse
from core.chunking import chunk

# ── parse ────────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  Parsing: {path.name}")
print(f"{'='*60}\n")

pages = parse(path)
print(f"[PARSE] {len(pages)} page(s) extracted\n")

for i, p in enumerate(pages):
    print(f"  Page {i}  |  heading: {p.heading!r}")
    preview = p.text[:200].replace("\n", " ")
    print(f"          |  text: {preview!r}{'...' if len(p.text) > 200 else ''}")
    print()

# ── chunk ────────────────────────────────────────────────────────────────────
print(f"{'='*60}")
print(f"  Chunking")
print(f"{'='*60}\n")

chunks = chunk(pages)
print(f"[CHUNK] {len(chunks)} chunk(s) produced\n")

for i, c in enumerate(chunks):
    print(f"  Chunk {i:02d}  |  tokens={c.token_count}  heading={c.heading!r}  page={c.doc_page}")
    preview = c.text[:300].replace("\n", " ")
    print(f"           |  {preview!r}{'...' if len(c.text) > 300 else ''}")
    print()
