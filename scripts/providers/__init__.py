"""Embedding provider base class."""
import json
import urllib.request
import urllib.error


class EmbeddingProvider:
    """Base class for embedding providers."""

    def init(self, api_key: str, api_base: str, model: str):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        POST {api_base}/embeddings
        Body: {"input": texts, "model": model}
        Returns: list of embedding vectors
        """
        url = f"{self.api_base}/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = json.dumps({"input": texts, "model": self.model}).encode()
        req = urllib.request.Request(
            url, data=payload, headers=headers, method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            print(f"HTTPError: {e.code} {e.reason}")
            raise
        except urllib.error.URLError as e:
            print(f"URLError: {e.reason}")
            raise

        sorted_embs = sorted(data["data"], key=lambda x: x["index"])
        return [e["embedding"] for e in sorted_embs]
