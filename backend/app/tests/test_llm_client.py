"""LLM client tests (SRS §9, §38.8).

Verifies the client is configurable and that provider/parse failures surface as
an honest :class:`LLMError` (rendered 503) rather than a fabricated result. No
network is used — the LiteLLM loader is monkeypatched.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.llm import LiteLLMClient, LLMError, build_llm_client


def test_build_llm_client_uses_configured_model() -> None:
    client = build_llm_client(Settings(llm_model="openai/gpt-4o", llm_temperature=0.0))
    assert isinstance(client, LiteLLMClient)
    assert client.model == "openai/gpt-4o"


async def test_complete_wraps_provider_errors_as_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(**kwargs: object) -> object:
        raise RuntimeError("no credentials configured")

    monkeypatch.setattr("app.llm.client._load_litellm_acompletion", lambda: boom)
    client = LiteLLMClient(model="anthropic/claude-opus-4-8")
    with pytest.raises(LLMError):
        await client.complete(system="s", user="u")


async def test_complete_parses_openai_shaped_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Msg:
        content = '{"ok": true}'

    class _Choice:
        message = _Msg()

    class _Usage:
        prompt_tokens = 11
        completion_tokens = 3

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()
        model = "resolved-model"

    async def ok(**kwargs: object) -> _Resp:
        # json_object should request strict JSON output where supported.
        assert kwargs.get("response_format") == {"type": "json_object"}
        # drop_params guards models that reject sampling/format params.
        assert kwargs.get("drop_params") is True
        return _Resp()

    monkeypatch.setattr("app.llm.client._load_litellm_acompletion", lambda: ok)
    client = LiteLLMClient(model="anthropic/claude-opus-4-8")
    result = await client.complete(system="s", user="u", json_object=True)
    assert result.text == '{"ok": true}'
    assert result.model == "resolved-model"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 3
