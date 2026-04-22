"""讯飞星火 MaaS v2 API — Embedding & Rerank provider.

Both endpoints use Bearer Token auth (same api_key value).
"""
import json
import urllib.request
import urllib.error


class SparkProvider:
    """讯飞星火 MaaS v2 Embedding + Rerank provider."""

    def init(self, api_key: str, api_base: str, embedding_model: str, rerank_model: str):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.embedding_model = embedding_model
        self.rerank_model = rerank_model

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.api_base}{path}"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise RuntimeError(f"Spark {path} HTTPError {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Spark {path} URLError: {e.reason}") from e

    def embed(self, texts: list[str]) -> list[list[float]]:
        """POST /v2/embeddings — returns list of embedding vectors."""
        resp = self._post("/embeddings", {
            "model": self.embedding_model,
            "input": texts,
        })
        sorted_embs = sorted(resp["data"], key=lambda x: x["index"])
        return [e["embedding"] for e in sorted_embs]

    def rerank(self, query: str, documents: list[str]) -> list[dict]:
        """POST /v2/rerank — returns list of {index, relevance_score}."""
        resp = self._post("/rerank", {
            "model": self.rerank_model,
            "query": query,
            "documents": documents,
        })
        return resp.get("results", [])
