"""OpenAI-compatible embedding provider."""
import json
import urllib.request
import urllib.error
import http.client
import time


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

        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    # Read all bytes — handle IncompleteRead gracefully
                    data = resp.read()
                    while True:
                        try:
                            data += resp.read()
                        except http.client.IncompleteRead:
                            break
                    return self._parse_response(data)
            except http.client.IncompleteRead as e:
                # Retry on incomplete read — server closed connection prematurely
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                print(f"IncompleteRead: {e}")
                raise
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                print(f"HTTPError: {e.code} {e.reason}")
                print(f"Response body: {body[:500]}")
                raise
            except urllib.error.URLError as e:
                print(f"URLError: {e.reason}")
                raise

    def _parse_response(self, raw: bytes) -> list[list[float]]:
        data = json.loads(raw)
        sorted_embs = sorted(data["data"], key=lambda x: x["index"])
        return [e["embedding"] for e in sorted_embs]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible embedding provider (used for both spark and openai)."""

    pass
