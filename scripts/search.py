#!/usr/bin/env python3
"""
Semantic memory search — query the chunk index with natural language.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sqlite3
import struct
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent


def load_config(config_path: str | None) -> dict:
    if config_path:
        p = Path(config_path)
    else:
        p = SKILL_DIR / "config.json"
    with open(p) as f:
        return json.load(f)


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    return conn


def blob_to_vector(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return max(0.0, dot)  # clip negative due to L2 rounding


def main():
    parser = argparse.ArgumentParser(description="Search semantic memory")
    parser.add_argument("query", help="Search query (natural language)")
    parser.add_argument("--workspace", help="Workspace path (overrides config)")
    parser.add_argument("--db", help="Database path (overrides config)")
    parser.add_argument("--provider", help="Provider name (overrides config)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument(
        "--min-score", type=float, default=0.3, help="Minimum similarity score (default: 0.3)"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument(
        "--config", help="Config file path (default: skill dir config.json)"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    indexing_cfg = config["indexing"]

    workspace = os.path.expanduser(args.workspace or indexing_cfg["workspace"])
    db_path = os.path.expanduser(args.db or indexing_cfg["db_path"])
    provider_name = args.provider or config["provider"]

    if not os.path.isabs(db_path):
        db_path = os.path.join(workspace, db_path)

    if not os.path.exists(db_path):
        print(f"Error: database not found at {db_path}")
        print("Run 'python scripts/index.py' first to build the index.")
        sys.exit(1)

    conn = init_db(db_path)

    sys.path.insert(0, str(SCRIPT_DIR))
    from init import get_provider

    provider = get_provider(provider_name, config)

    # Embed query
    try:
        query_embedding = provider.embed([args.query])[0]
    except Exception as e:
        print(f"Error: failed to embed query: {e}")
        sys.exit(1)

    # L2 normalize (provider may or may not return normalized vectors)
    norm = math.sqrt(sum(x * x for x in query_embedding))
    if norm == 0:
        query_embedding = query_embedding
    else:
        query_embedding = [x / norm for x in query_embedding]

    # Load all chunks
    rows = conn.execute(
        "SELECT id, file_path, line_start, line_end, content, embedding FROM chunks"
    ).fetchall()

    if not rows:
        print("Index is empty. Run 'python scripts/index.py' first.")
        sys.exit(1)

    # Score each chunk
    scored = []
    for row in rows:
        chunk_id, fpath, line_start, line_end, content, blob = row
        vec = blob_to_vector(blob)
        score = cosine_similarity(query_embedding, vec)
        if score >= args.min_score:
            scored.append((score, fpath, line_start, line_end, content))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: args.top_k]

    if not top:
        print("No results above minimum score threshold.")
        return

    if args.json:
        import json as jsonlib

        results = [
            {
                "score": round(s, 4),
                "file": fp,
                "line_start": ls,
                "line_end": le,
                "content": content,
            }
            for s, fp, ls, le, content in top
        ]
        print(jsonlib.dumps(results, ensure_ascii=False, indent=2))
    else:
        for rank, (score, fpath, line_start, line_end, content) in enumerate(top, 1):
            rel = os.path.relpath(fpath, workspace)
            snippet = content[:200].replace("\n", " ").strip()
            print(f"--- Result {rank} (score={score:.4f}) ---")
            print(f"File: {rel}  lines {line_start}-{line_end}")
            print(f"     {snippet}")
            print()

    conn.close()


if __name__ == "__main__":
    main()
