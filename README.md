# hermes-semantic-memory

Hermes Agent 的语义搜索技能 — 对工作区中的 Markdown 文件进行语义检索，基于 Embedding API + SQLite 向量存储，纯 Python 标准库实现，零额外依赖。

专为 [Hermes Agent](https://github.com/yan-wyb/hermes) 设计，可作为长期记忆和工作区知识库检索工具。

## 工作原理

```
.md 文件 → 切 chunk → Embedding API → 向量存入 SQLite
                                            ↓
用户查询 → Embedding API → 查询向量 → 余弦相似度 → Top-K 结果
```

## 快速开始

### 1. 克隆到 Hermes skills 目录

```bash
mkdir -p ~/.hermes/skills
git clone https://github.com/toller892/hermes-semantic-memory.git \
  ~/.hermes/skills/semantic-memory
```

### 2. 配置 API（讯飞星火示例）

```bash
export EMBEDDING_API_KEY="your-api-key"
export EMBEDDING_API_BASE="https://maas-api.cn-huabei-1.xf-yun.com/v2"
export EMBEDDING_MODEL="xop3qwen8bembedding"   # 768 维向量
```

> 支持任何 OpenAI `/v1/embeddings` 兼容接口（OpenAI、Gemini、Ollama、本地模型等）

### 3. 建索引

```bash
python3 ~/.hermes/skills/semantic-memory/scripts/index.py \
  ~/.openclaw/workspace
```

### 4. 搜索

```bash
python3 ~/.hermes/skills/semantic-memory/scripts/search.py \
  "我之前关于数据库选型是怎么考虑的"
```

## 命令详解

### index.py — 构建索引

```bash
python3 scripts/index.py /path/to/workspace [选项]
```

| 选项 | 说明 |
|------|------|
| `--db PATH` | SQLite 数据库路径（默认：`memory.sqlite`） |
| `--api-base URL` | Embedding API 地址 |
| `--api-key KEY` | API Key |
| `--model NAME` | Embedding 模型名 |
| `--force` | 清空已有索引，全量重建 |

- **增量索引**：基于内容 MD5 哈希，只处理新增/修改的 chunk
- **自动清理**：已删除文件的索引记录会被清除
- **批量请求**：每批 10 条，避免 API 超时

### search.py — 语义搜索

```bash
python3 scripts/search.py "查询内容" [选项]
```

| 选项 | 说明 |
|------|------|
| `--db PATH` | SQLite 数据库路径 |
| `--api-base URL` | Embedding API 地址 |
| `--api-key KEY` | API Key |
| `--model NAME` | Embedding 模型名 |
| `--top-k N` | 返回结果数（默认：5） |
| `--min-score F` | 最低相似度阈值（默认：0.3） |
| `--json` | 以 JSON 格式输出 |

## 环境变量

所有参数均可通过环境变量设置，命令行参数优先级更高：

| 环境变量 | 说明 |
|----------|------|
| `EMBEDDING_API_KEY` | API Key（必填） |
| `EMBEDDING_API_BASE` | API 地址（默认：`https://api.openai.com/v1`） |
| `EMBEDDING_MODEL` | 模型名（默认：`text-embedding-3-small`） |
| `MSS_DB` | SQLite 数据库路径 |
| `MSS_TOP_K` | 搜索返回数量 |
| `MSS_MIN_SCORE` | 最低相似度阈值 |

## 技术细节

- **Chunk 策略**：按行切分，目标 ~400 token/chunk，80 token 重叠
- **向量存储**：SQLite + 二进制 blob（`struct.pack` 打包 float32 数组）
- **相似度**：余弦相似度，向量已 L2 归一化后简化为点积运算
- **增量索引**：MD5 哈希判断 chunk 是否变更
- **批量 embedding**：每批 10 条

## 兼容的 Embedding API

任何兼容 OpenAI `/v1/embeddings` 接口的服务均可：

| 服务 | 模型示例 | 向量维度 |
|------|----------|----------|
| 讯飞星火 | `xop3qwen8bembedding` | 768 |
| OpenAI | `text-embedding-3-small` | 1536 |
| OpenAI | `text-embedding-3-large` | 3072 |
| Ollama | `nomic-embed-text` | 768 |
| Gemini | `text-embedding-004` | 768 |

## Hermes 中的用法

在 Hermes 对话中，当用户描述他们想找的内容但记不清具体文字时，使用此技能：

```
User: 我之前好像写过关于微服务容错的内容，在哪个文件来着？
→ semantic-memory: "微服务容错设计" → 找到相关 markdown 文件和段落
```

Skill 会自动加载 `semantic-memory`，用户无需手动调用脚本。

## License

MIT
