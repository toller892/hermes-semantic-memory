#!/usr/bin/env python3
"""
Semantic memory indexer — build / update chunk embeddings in SQLite.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import hashlib
import sqlite3
import struct
import sys
from pathlib import Path
from typing import List, Tuple

# Resolve skill directory relative to this script
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent


def load_config(config_path: str | None) -> dict:
    if config_path:
        p = Path(config_path)
    else:
        p = SKILL_DIR / "config.json"
    with open(p) as f:
        return json.load(f)


def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path    TEXT NOT NULL,
            line_start   INTEGER NOT NULL,
            line_end     INTEGER NOT NULL,
            content      TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding    BLOB NOT NULL,
            UNIQUE(file_path, line_start, content_hash)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON chunks(file_path)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hash ON chunks(content_hash)")
    conn.commit()
    return conn


def get_existing_hashes(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT file_path, line_start, content_hash FROM chunks")
    return {(r[0], r[1], r[2]) for r in rows}


def get_indexed_files(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT DISTINCT file_path FROM chunks")
    return {r[0] for r in rows}


def chunk_text(
    lines: list[str], chunk_size: int, chunk_overlap: int
) -> list[tuple[int, int, str]]:
    """
    Sliding-window chunking over lines.
    Returns list of (line_start, line_end, content) where line_start/end are 1-indexed.
    """
    result = []
    n = len(lines)
    if n == 0:
        return result

    start = 0
    while start < n:
        end = start + 1
        char_count = len(lines[start])
        while end < n and char_count < chunk_size:
            char_count += len(lines[end])
            end += 1

        # clamp
        chunk_lines = lines[start:end]
        content = "".join(chunk_lines)

        result.append((start + 1, end, content))

        if end >= n:
            break

        # step back by overlap lines
        overlap_chars = 0
        step_back = 0
        for i in range(len(chunk_lines) - 1, 0, -1):
            overlap_chars += len(chunk_lines[i])
            step_back += 1
            if overlap_chars >= chunk_overlap:
                break
        start = max(start + 1, start + step_back)

    return result


def content_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def vector_to_blob(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def blob_to_vector(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot  # both already L2-normalized


def walk_markdown(workspace: str, exclude_dirs: list[str]) -> list[str]:
    workspace = os.path.expanduser(workspace)
    exclude = set(exclude_dirs)
    md_files = []
    for root, dirs, files in os.walk(workspace):
        # Prune excluded dirs in-place so os.walk doesn't descend
        dirs[:] = [d for d in dirs if d not in exclude]
        for fname in files:
            if fname.endswith(".md"):
                md_files.append(os.path.join(root, fname))
    return md_files


def main():
    parser = argparse.ArgumentParser(description="Build / update semantic index")
    parser.add_argument("--workspace", help="Workspace path (overrides config)")
    parser.add_argument("--db", help="Database path (overrides config)")
    parser.add_argument("--provider", help="Provider name (overrides config)")
    parser.add_argument("--reindex", action="store_true", help="Force full rebuild")
    parser.add_argument(
        "--config", help="Config file path (default: skill dir config.json)"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    indexing_cfg = config["indexing"]

    workspace = os.path.expanduser(args.workspace or indexing_cfg["workspace"])
    db_path = os.path.expanduser(args.db or indexing_cfg["db_path"])
    provider_name = args.provider or config["provider"]
    chunk_size = indexing_cfg["chunk_size"]
    chunk_overlap = indexing_cfg["chunk_overlap"]
    exclude_dirs = indexing_cfg["exclude_dirs"]

    if not os.path.isdir(workspace):
        print(f"Error: workspace not found: {workspace}")
        sys.exit(1)

    # Resolve db path relative to workspace for convenience
    if not os.path.isabs(db_path):
        db_path = os.path.join(workspace, db_path)

    conn = init_db(db_path)

    if args.reindex:
        conn.execute("DELETE FROM chunks")
        conn.commit()
        print("Full rebuild triggered — all existing chunks deleted.")

    # Add scripts directory to path for get_provider
    sys.path.insert(0, str(SCRIPT_DIR))
    from init import get_provider

    provider = get_provider(provider_name, config)

    # --- Phase 1: discover all markdown files ---
    md_files = walk_markdown(workspace, exclude_dirs)
    current_files = set(md_files)

    # --- Phase 2: remove stale entries ---
    indexed_files = get_indexed_files(conn)
    stale = indexed_files - current_files
    if stale:
        for f in stale:
            conn.execute("DELETE FROM chunks WHERE file_path = ?", (f,))
        conn.commit()
        print(f"Removed {len(stale)} stale file(s) from index.")

    # --- Phase 3: collect chunks needing embedding ---
    existing = get_existing_hashes(conn)
    to_embed = []  # list of (file_path, line_start, line_end, content)

    for fpath in md_files:
        try:
            with open(fpath) as f:
                raw = f.read()
        except PermissionError:
            print(f"Warning: cannot read {fpath} — skipping")
            continue
        except Exception as e:
            print(f"Warning: error reading {fpath}: {e} — skipping")
            continue

        if raw == "":
            continue

        lines = raw.splitlines(keepends=False)
        chunks = chunk_text(lines, chunk_size, chunk_overlap)

        for line_start, line_end, content in chunks:
            h = content_hash(content)
            key = (fpath, line_start, h)
            if key not in existing:
                to_embed.append((fpath, line_start, line_end, content))

    if not to_embed:
        print("Nothing to index — all chunks up to date.")
        return

    print(f"Indexing {len(to_embed)} new chunk(s)...")

    # --- Phase 4: batch embed and write ---
    BATCH = 16
    total = len(to_embed)

    for i in range(0, total, BATCH):
        batch = to_embed[i : i + BATCH]
        texts = [item[3] for item in batch]

        try:
            embeddings = provider.embed(texts)
        except Exception as e:
            print(f"API error during batch {i//BATCH + 1}: {e}")
            sys.exit(1)

        for (fpath, line_start, line_end, content), emb in zip(batch, embeddings):
            h = content_hash(content)
            normalized = l2_normalize(emb)
            blob = vector_to_blob(normalized)
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO chunks (file_path, line_start, line_end, content, content_hash, embedding) VALUES (?, ?, ?, ?, ?, ?)",
                    (fpath, line_start, line_end, content, h, blob),
                )
            except Exception as e:
                print(f"DB error inserting chunk from {fpath}: {e}")

        conn.commit()
        print(f"  Batch {i//BATCH + 1}/{(total + BATCH - 1)//BATCH} — {min(i+BATCH, total)}/{total} done")

    print(f"Indexing complete. {total} chunk(s) added / updated.")


if __name__ == "__main__":
    main()
