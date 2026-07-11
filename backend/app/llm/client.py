"""Configurable LLM client for the AI pipeline (SRS §9, §14.14, §6.5).

The Planner (SRS §14) and Synthesizer (SRS §6.5) are the *only* AI components in
Terra. Both talk to a single, provider-agnostic completion interface —
:class:`LLMClient` — so the concrete model is a configuration choice, never
hardcoded (SRS §9: "LangChain, LiteLLM, OpenAI / Claude (configurable)").

:class:`LiteLLMClient` is the production implementation. It routes to any
provider LiteLLM supports (Anthropic, OpenAI, …) via the ``TERRA_LLM_MODEL``
route string, defaulting to a current Claude model. ``litellm`` is imported
lazily so the dependency is optional: tests inject a fake client and the
deterministic Fetch spine (SRS §15) never needs it.

Determinism (SRS §14.13): the client requests ``temperature=0``. Some current
models (e.g. Claude Opus 4.8 / Sonnet 5) reject sampling parameters with a 400,
so ``drop_params`` lets LiteLLM silently drop unsupported knobs — the parameter
is honoured where supported and dropped where not, never causing a hard failure.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from app.core.config import Settings, get_settings
from app.core.errors import AppError, RateLimitError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMError(AppError):
    """The language model is unavailable or failed (SRS §38.8).

    Rendered as ``503`` so ``/ask`` degrades honestly — the platform never
    fabricates a plan or answer when the model cannot be reached.
    """

    code = "LLM_UNAVAILABLE"
    status_code = 503
    message = "The language model required for /api/v1/ask is unavailable."


class LLMResult(BaseModel):
    """A single completion result (SRS §14.18 telemetry)."""

    model_config = ConfigDict(frozen=True)

    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@runtime_checkable
class LLMClient(Protocol):
    """Minimal completion interface the Planner and Synthesizer depend on.

    A single-shot, stateless ``system + user -> text`` call. ``json_object``
    asks the provider for strict JSON output where supported; callers must still
    parse defensively (SRS §14.15).
    """

    @property
    def model(self) -> str: ...

    async def complete(self, *, system: str, user: str, json_object: bool = False) -> LLMResult: ...


class LiteLLMClient:
    """LiteLLM-backed, provider-agnostic completion client (SRS §9)."""

    def __init__(
        self,
        *,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        timeout: float = 30.0,
        api_key: str | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._api_key = api_key
        self._reasoning_effort = reasoning_effort

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, *, system: str, user: str, json_object: bool = False) -> LLMResult:
        """Run one completion, returning the assistant text (SRS §14.6)."""
        acompletion = _load_litellm_acompletion()
        kwargs: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "timeout": self._timeout,
            # Silently drop provider-unsupported params (e.g. temperature on
            # Claude Opus 4.8 / Sonnet 5) instead of 400ing — keeps the model
            # configurable without per-provider special-casing.
            "drop_params": True,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._reasoning_effort:
            # "disable" turns off Gemini 2.5's thinking, which otherwise burns
            # the max_tokens budget on hidden reasoning and truncates the
            # visible answer. Dropped harmlessly where unsupported (drop_params).
            kwargs["reasoning_effort"] = self._reasoning_effort
        if json_object:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await acompletion(**kwargs)
        except Exception as exc:
            logger.warning("llm.completion_failed", model=self._model, error=str(exc))
            # A provider rate/quota limit (e.g. Gemini's free-tier daily request
            # cap) is the caller's to retry later, not an outage — surfaced as
            # 429 rather than the generic 503 so it reads correctly. The
            # provider's own retry-delay hint is unreliable for daily quotas
            # (it can suggest seconds against a limit that resets at midnight),
            # so no Retry-After is set rather than promise a wrong wait time.
            if _is_provider_rate_limit(exc):
                raise RateLimitError(
                    "The language model provider's request quota is exhausted for now. "
                    "Please try again later."
                ) from exc
            raise LLMError(  # provider/auth/network errors -> honest 503
                "The language model request failed.",
                details=f"{type(exc).__name__}: {exc}",
            ) from exc

        return _to_result(response, self._model)


def _is_provider_rate_limit(exc: Exception) -> bool:
    """Whether ``exc`` is the provider's own rate/quota limit (not a local error)."""
    try:
        import litellm  # noqa: PLC0415 (lazy — see module docstring)
    except ImportError:  # pragma: no cover - litellm always installed to reach here
        return False
    return isinstance(exc, litellm.RateLimitError)


def _load_litellm_acompletion():  # type: ignore[no-untyped-def]
    """Import ``litellm.acompletion`` lazily, or raise a clear 503 (SRS §38.8)."""
    try:
        import litellm
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        raise LLMError(
            "The 'litellm' package is required for /api/v1/ask but is not installed.",
            details="Install the AI dependencies to enable natural-language queries.",
        ) from exc
    return litellm.acompletion


def _to_result(response: object, model: str) -> LLMResult:
    """Extract text + token usage from a LiteLLM (OpenAI-shaped) response."""
    try:
        choices = response.choices  # type: ignore[attr-defined]
        text = choices[0].message.content or ""
    except (AttributeError, IndexError, TypeError) as exc:  # pragma: no cover - defensive
        raise LLMError(
            "The language model returned an unreadable response.",
            details=f"{type(exc).__name__}: {exc}",
        ) from exc

    usage = getattr(response, "usage", None)
    return LLMResult(
        text=text,
        model=getattr(response, "model", None) or model,
        prompt_tokens=_usage_int(usage, "prompt_tokens"),
        completion_tokens=_usage_int(usage, "completion_tokens"),
    )


def _usage_int(usage: object, key: str) -> int | None:
    if usage is None:
        return None
    value = getattr(usage, key, None)
    if value is None and isinstance(usage, dict):
        value = usage.get(key)  # type: ignore[unreachable]
    return int(value) if isinstance(value, (int, float)) else None


def build_llm_client(settings: Settings | None = None) -> LLMClient:
    """Construct the production LLM client from settings (SRS §9)."""
    settings = settings or get_settings()
    return LiteLLMClient(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
        api_key=settings.llm_api_key,
        reasoning_effort=settings.llm_reasoning_effort,
    )


__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResult",
    "LiteLLMClient",
    "build_llm_client",
]
