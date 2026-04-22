---
name: semantic-memory
description: "Hermes workspace semantic search — find anything by meaning, not keywords. Indexes markdown files in the workspace using OpenAI-compatible Embedding API + SQLite. Use when: (1) user asks to find something they wrote but can't remember exact words, (2) searching session memory or notes by concept, (3) recalling past decisions, context, or documentation semantically. NOT for: exact-match searches, non-text files, web search, or code search (use grep/symbol lookup instead)."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [memory, search, semantic, rag, embedding, workspace]
    category: productivity
    related_skills: [llm-wiki, obsidian]
---

# Semantic Memory Search

Semantic search over workspace markdown files using OpenAI-compatible Embedding API + SQLite vector store. Finds content by *meaning*, not keywords.

## How It Works

```
.md files → sliding-window chunk (400 chars, 80 overlap) → Embedding API → SQLite vector DB
                                                              ↓
User query → Embedding API → query vector → cosine similarity → Top-K results
```

- **Chunk strategy:** 400 chars/chunk, 80-char overlap, MD5 deduplication
- **Vector storage:** SQLite BLOB (struct.pack float arrays), L2 normalized
- **Similarity:** Cosine similarity (dot product after L2 norm)
- **Incremental indexing:** MD5-based change detection, auto-cleanup of deleted files
- **Batch embedding:** 16 chunks/batch
- **Dependencies:** Pure Python stdlib only

## Setup

Edit `~/.hermes/skills/semantic-memory/config.json`:

```json
{
  "provider": "spark",
  "spark": {
    "api_key": "your-spark-api-key",
    "api_base": "https://maas-api.cn-huabei-1.xf-yun.com/v2",
    "embedding_model": "sde0a5839",
    "rerank_model": "s125c8e0e"
  },
  "openai": {
    "api_key": "your-openai-api-key",
    "api_base": "https://api.openai.com/v1",
    "model": "text-embedding-3-small"
  },
  "indexing": {
    "workspace": "~/.openclaw/workspace",
    "db_path": "memory.sqlite",
    "chunk_size": 400,
    "chunk_overlap": 80,
    "exclude_dirs": [".git", "node_modules", "__pycache__", ".venv", "venv", ".obsidian"]
  }
}
```

> **讯飞 Spark MaaS v2 注意：** `api_key` 使用控制台获取的 APIKey 值（Bearer Token 认证）。`embedding_model` 和 `rerank_model` 是分别的模型 ID。切换 provider 只需改 `"provider": "openai"` 并填 `openai` 的字段。

Switch provider by changing `"provider": "spark"` to `"provider": "openai"`.

## Index a Workspace

```bash
python3 ~/.hermes/skills/semantic-memory/scripts/index.py
```

Options:
- `--workspace PATH` — override workspace path
- `--db PATH` — override database path
- `--provider NAME` — override provider (spark / openai)
- `--reindex` — force full rebuild (delete all existing chunks first)
- `--config PATH` — override config file path

Incremental by default: only new/changed chunks are embedded. Deleted files are auto-cleaned from DB.

## Search

```bash
python3 ~/.hermes/skills/semantic-memory/scripts/search.py "what was that decision about database"
```

Options:
- `--top-k N` — number of results (default: 5)
- `--min-score F` — minimum cosine similarity threshold (default: 0.3)
- `--json` — output as JSON for programmatic use
- `--workspace`, `--db`, `--provider`, `--config` — same as index

## Agent Workflow

### Typical usage pattern:

1. **First time:** Run `index.py` on the workspace
2. **After changes:** Re-run `index.py` — incremental update handles additions/changes
3. **To find something:** Run `search.py "conceptual query"`
4. **Load full context:** Use results' file paths + line numbers with `read_file`

### When to use this vs. grep:

| Task | Tool |
|------|------|
| Remembered exact words/phrases | `search_files` (grep-style) |
| Know concept but not the wording | `semantic-memory` (this skill) |
| Find related decisions across files | `semantic-memory` |
| Recall past context from memory notes | `semantic-memory` |
| Search code by symbol/function name | `search_files` |
| Find files by name | `search_files(target="files")` |

## File Structure

```
~/.hermes/skills/semantic-memory/
├── SKILL.md                        # This file
├── config.json                     # Global configuration
└── scripts/
    ├── init.py                     # get_provider() — runtime provider loader
    ├── index.py                    # Build / update index
    ├── search.py                   # Search the index
    └── providers/
        ├── __init__.py            # EmbeddingProvider base class
        ├── openai.py              # OpenAI-compatible provider
        └── spark.py               # Spark MaaS v2 provider (Bearer Token)
```

## Compatible Embedding APIs

Any service exposing an OpenAI-compatible `/embeddings` endpoint:

- Spark (讯飞星火) — `provider: "spark"`, embedding_model: `sde0a5839`, rerank_model: `s125c8e0e`
- OpenAI (text-embedding-3-small / text-embedding-3-large)
- Azure OpenAI
- Gemini Embedding
- Ollama (local: `http://localhost:11434`)
- Fireworks AI / Groq
- Any OpenAI-compatible proxy

## Tips

- **Index size:** ~100-200 chunks per MB of markdown. A 10MB workspace ≈ 1500-2000 chunks.
- **Speed:** Indexing is the slow part (API calls). Searching is fast (<1s for 10K chunks).
- **Overlap helps:** The 80-char overlap ensures concepts at chunk boundaries aren't lost.
- **min-score:** Lower = more results but lower quality. 0.3-0.5 is usually a good range.
- **top-k:** More results give better coverage but more noise. 5-10 is usually enough.

## Troubleshooting

**"API key for provider 'spark' is not set" error:**
→ Set `api_key` in the `spark` section of `config.json`.

**讯飞 Spark 401 认证错误：**
讯飞 MaaS v2 使用 Bearer Token 认证（`Authorization: Bearer <key>`）。如果报 401，检查：1) `api_key` 是否正确；2) `api_base` 是否以 `/v2` 结尾；3) `embedding_model` 是否与控制台模型 ID 一致。

**"Database not found" error:**
→ Run `index.py` first to create the database.

**"Nothing to index — all chunks up to date" but index is empty:**
→ The database might be at a different path. Use `--db PATH` to specify location.

**Indexing interrupted (IncompleteRead / timeout):**
→ Just re-run `index.py` without `--reindex`. Incremental mode skips already-indexed chunks and picks up where it left off. No need to start over.

**Poor search results:**
- Try lowering `--min-score` to 0.25 or 0.2
- Try re-indexing with `--reindex` if the workspace changed significantly
- Consider whether your query describes a *concept* rather than specific words

## Architecture Notes

**Provider abstraction works as designed:** `index.py` and `search.py` contain zero provider logic. Switching from `spark` to `openai` was a one-line config change. Adding a new provider = adding one file in `providers/` + one `get_provider()` branch in `scripts/init.py` + updating `config.json`.

**Pure stdlib confirmed:** All source files use only `json / urllib.request / sqlite3 / hashlib / struct / math / argparse / os`. No external dependencies needed.

**Python 3.9 compatible:** All type annotations use `from __future__ import annotations` pattern where needed.

**Incremental indexing verified:** The MD5-based change detection correctly skips unchanged chunks. Deleted files are auto-removed from DB on re-index.
