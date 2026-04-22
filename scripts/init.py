"""Provider loader — returns the right EmbeddingProvider instance based on name."""
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent


def get_provider(name: str, config: dict):
    """
    Load and return an EmbeddingProvider instance.

    Args:
        name: provider name ("openai" or "spark")
        config: full config dict

    Returns:
        EmbeddingProvider instance
    """
    provider_config = config.get(name, {})
    api_key = provider_config.get("api_key", "")
    api_base = provider_config.get("api_base", "")

    if not api_key:
        raise ValueError(f"API key for provider '{name}' is not set in config.json")

    if name == "spark":
        providers_dir = SKILL_DIR / "scripts" / "providers"
        if str(providers_dir) not in sys.path:
            sys.path.insert(0, str(providers_dir))
        from spark import SparkProvider
        provider = SparkProvider()
        provider.init(
            api_key=api_key,
            api_base=api_base,
            embedding_model=provider_config.get("embedding_model", ""),
            rerank_model=provider_config.get("rerank_model", ""),
        )
    else:
        providers_dir = SKILL_DIR / "scripts" / "providers"
        if str(providers_dir) not in sys.path:
            sys.path.insert(0, str(providers_dir))
        from openai import OpenAIEmbeddingProvider
        provider = OpenAIEmbeddingProvider()
        model = provider_config.get(
            "embedding_model",
            provider_config.get("model", ""),
        )
        provider.init(api_key=api_key, api_base=api_base, model=model)

    return provider
