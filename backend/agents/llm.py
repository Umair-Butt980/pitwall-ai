"""Shared, pre-configured Claude clients for the agent pipeline.

≈ a NestJS provider registered once and injected everywhere. Building a new
ChatAnthropic per node call wastes connections and, worse, ships without any
cost guards — every client here is capped with max_tokens / timeout / retries.
"""
from __future__ import annotations

from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from config import get_settings

# Haiku 4.5 is fast and cheap — sufficient for the seven analysis agents.
# Sonnet 4.6 is reserved for the final prediction synthesis.
HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"


@lru_cache(maxsize=None)
def get_llm(model: str, max_tokens: int = 1500) -> ChatAnthropic:
    """One client per (model, max_tokens) pair, created lazily and reused.

    timeout stops a hung API call from stalling a prediction forever;
    max_tokens is a hard per-call spend ceiling.
    """
    return ChatAnthropic(
        model=model,
        api_key=get_settings().anthropic_api_key,
        max_tokens=max_tokens,
        timeout=60.0,
        max_retries=2,
    )
