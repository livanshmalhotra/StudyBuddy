"""
scripts/eval_search.py — evaluate hybrid search hit rate
Usage:
    python scripts/eval_search.py --queries scripts/eval_queries.yaml

Output:
    Query 1: ✅ Top-3 hit  (rank 1, score 0.82)
    Query 2: ❌ Not found
    ...
    Top-3 hit rate: 7/10 (70%)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx
import yaml  # pip install pyyaml

API_BASE = "http://localhost:8000"


def run_eval(queries_file: str):
    data = yaml.safe_load(Path(queries_file).read_text())
    queries = data.get("queries", [])
    if not queries:
        print("No queries found in YAML.")
        return

    hits = 0
    for i, q in enumerate(queries, start=1):
        question = q["question"]
        expected_filename = q.get("expected_filename")
        expected_substring = q.get("expected_substring")

        resp = httpx.post(
            f"{API_BASE}/search",
            json={"query": question, "k": 3},
            timeout=30.0,
        )
        resp.raise_for_status()
        results = resp.json()

        hit = False
        rank = None
        score = None
        for j, r in enumerate(results, start=1):
            filename_match = (not expected_filename) or r["filename"] == expected_filename
            text_match = (not expected_substring) or expected_substring.lower() in r["text"].lower()
            if filename_match and text_match:
                hit = True
                rank = j
                score = r["fused_score"]
                break

        if hit:
            hits += 1
            print(f"  Query {i}: ✅ Top-3 hit  (rank {rank}, score {score:.4f})")
            print(f"           {question!r}")
        else:
            print(f"  Query {i}: ❌ Not found")
            print(f"           {question!r}")

    total = len(queries)
    pct = int(100 * hits / total) if total else 0
    print(f"\nTop-3 hit rate: {hits}/{total} ({pct}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", required=True, help="Path to eval_queries.yaml")
    args = parser.parse_args()
    run_eval(args.queries)
