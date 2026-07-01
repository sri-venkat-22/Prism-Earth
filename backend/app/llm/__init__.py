"""Configurable LLM access for the AI pipeline (SRS §9).

The Planner (SRS §14) and Synthesizer (SRS §6.5) depend on the provider-agnostic
:class:`LLMClient` interface; everything else in the platform is deterministic
(SRS §15, §38.3). Import the public surface from here:

    from app.llm import LLMClient, LLMError, build_llm_client
"""

from __future__ import annotations

from app.llm.client import (
    LiteLLMClient,
    LLMClient,
    LLMError,
    LLMResult,
    build_llm_client,
)

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResult",
    "LiteLLMClient",
    "build_llm_client",
]
