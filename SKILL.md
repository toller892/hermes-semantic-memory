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
.md files → chunk (~400 tokens) → Embedding API → SQLite vector DB
                                                    ↓
User query → Embedding API → query vector → cosine similarity → Top-K results
```

- **Chunk strategy:** ~400 tokens/chunk, 80-token overlap between chunks
- **Vector storage:** SQLite + binary blob (struct.pack float arrays)
- **Similarity:** Cosine similarity
- **Incremental indexing:** MD5-based change detection, auto-cleanup of deleted files
- **Batch embedding:** 10 chunks/batch to avoid API timeout
- **Dependencies:** Pure Python stdlib + any OpenAI-compatible embedding API

## Setup

Set environment variables (or pass as CLI args — CLI takes priority):

```bash
export EMBEDDING_API_KEY="your-api-key"
export EMBEDDING_API_BASE="https://api.openai.com/v1"   # any OpenAI-compatible endpoint
export EMBEDDING_MODEL="text-embedding-3-small"          # optional, default
```

## Index a Workspace

```bash
python3 ~/.hermes/skills/semantic-memory/scripts/index.py /path/to/workspace
```

Options:
- `--force` — clear existing index and rebuild from scratch
- `--db PATH` — custom SQLite path (default: `~/.hermes/skills/semantic-memory/memory.sqlite`)
- `--api-base`, `--api-key`, `--model` — override env vars

Incremental by default: only new/changed chunks are embedded. Deleted files are auto-cleaned.

## Search

```bash
python3 ~/.hermes/skills/semantic-memory/scripts/search.py "what was that decision about the database"
```

Options:
- `--top-k N` — number of results (default: 5)
- `--min-score F` — minimum cosine similarity threshold (default: 0.3)
- `--json` — output as JSON for programmatic use
- `--db`, `--api-base`, `--api-key`, `--model` — same as index

## Agent Workflow

### Typical usage pattern:

1. **First time:** Run `index.py` on the workspace (or relevant subdirectory)
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

## Configuration Reference

| Env Variable | CLI Flag | Default | Description |
|-------------|----------|---------|-------------|
| `EMBEDDING_API_KEY` | `--api-key` | (required) | API key for embedding service |
| `EMBEDDING_API_BASE` | `--api-base` | `https://api.openai.com/v1` | API endpoint URL |
| `EMBEDDING_MODEL` | `--model` | `text-embedding-3-small` | Embedding model name |
| `SEMANTIC_DB` | `--db` | `~/.hermes/skills/semantic-memory/memory.sqlite` | SQLite database path |
| `SEMANTIC_TOP_K` | `--top-k` | `5` | Default result count |
| `SEMANTIC_MIN_SCORE` | `--min-score` | `0.3` | Minimum similarity threshold |

## Compatible Embedding APIs

Any service exposing an OpenAI-compatible `/v1/embeddings` endpoint:

- OpenAI (text-embedding-3-small / text-embedding-3-large)
- Azure OpenAI
- Gemini Embedding
- Ollama (local: `http://localhost:11434`)
- Fireworks AI
- Groq
- Any OpenAI-compatible proxy

## Tips

- **Index size:** ~100-200 chunks per MB of markdown. A 10MB workspace ≈ 1500-2000 chunks.
- **Speed:** Indexing is the slow part (API calls). Searching is fast (<1s for 10K chunks).
- **Overlap helps:** The 80-token overlap ensures concepts at chunk boundaries aren't lost.
- **min-score:** Lower = more results but lower quality. 0.3-0.5 is usually a good range.
- **top-k:** More results give better coverage but more noise. 5-10 is usually enough.
- **Batch size:** 10 chunks per API call — balances speed vs. timeout risk.

## Troubleshooting

**"No API key" error:**
```bash
export EMBEDDING_API_KEY="sk-..."
```

**"Database not found" error:**
Run `index.py` first to create the database.

**"No indexed chunks" error:**
Either the database is empty or was cleared. Re-run `index.py`.

**Poor search results:**
- Try lowering `--min-score` to 0.25 or 0.2
- Try re-indexing with `--force` if the workspace changed significantly
- Consider whether your query describes a *concept* rather than specific words
