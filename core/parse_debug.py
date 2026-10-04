import sys
from pathlib import Path
from core.parsing import parse
from core.chunking import chunk

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m core.parse_debug <path_to_file>")
        sys.exit(1)
        
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)
        
    print(f"Parsing {path}...")
    pages = parse(path)
    print(f"Parsed {len(pages)} pages.")
    
    chunks = chunk(pages)
    print(f"Created {len(chunks)} chunks.\n")
    
    for i, c in enumerate(chunks):
        print(f"[chunk {i+1}] page={c.doc_page} heading={c.heading!r} tokens={c.token_count}")
        print(f"text: {c.text[:100]}...")
        print("-" * 40)

if __name__ == "__main__":
    main()
