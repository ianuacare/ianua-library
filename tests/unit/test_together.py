"""Together provider."""

from unittest.mock import MagicMock, patch

import pytest

import ianuacare.ai.providers.together as together_module
from ianuacare.ai.providers.together import TogetherAIProvider


def test_together_infer() -> None:
    mock_together_cls = MagicMock()
    client = MagicMock()
    mock_together_cls.return_value = client
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="ok"))]
    response.model_dump.return_value = {"id": "x"}
    client.chat.completions.create.return_value = response

    with patch.object(together_module, "Together", mock_together_cls):
        provider = TogetherAIProvider(api_key="k", default_model="m")
        out = provider.infer("m", "hello")
        assert out["content"] == "ok"
        assert out["model"] == "m"


def test_together_infer_embeddings() -> None:
    mock_together_cls = MagicMock()
    client = MagicMock()
    mock_together_cls.return_value = client
    emb_resp = MagicMock()
    emb_rows: list[MagicMock] = []
    for index in range(2):
        row = MagicMock()
        row.index = index
        row.embedding = [0.1 * index, 0.2]
        emb_rows.append(row)
    emb_resp.data = emb_rows
    client.embeddings.create.return_value = emb_resp

    with patch.object(together_module, "Together", mock_together_cls):
        provider = TogetherAIProvider(api_key="k", default_model="embed-model")
        out = provider.infer("mx", ["a", "b"], model_type="embedding")
        assert out == [[0.0, 0.2], [0.1, 0.2]]
        client.embeddings.create.assert_called_once_with(
            model="mx", input=["a", "b"]
        )
        client.chat.completions.create.assert_not_called()


def test_together_infer_accepts_messages_list() -> None:
    """Provider passes a pre-built messages list straight to the API."""
    mock_together_cls = MagicMock()
    client = MagicMock()
    mock_together_cls.return_value = client
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="risposta"))]
    response.model_dump.return_value = {}
    client.chat.completions.create.return_value = response

    messages = [
        {"role": "system", "content": "Sei un assistente."},
        {"role": "user", "content": "[RETRIEVED CONTEXT]\nDoc A\n\nDomanda?"},
    ]

    with patch.object(together_module, "Together", mock_together_cls):
        provider = TogetherAIProvider(api_key="k", default_model="m")
        out = provider.infer("m", messages)
        assert out["text"] == "risposta"
        call_kwargs = client.chat.completions.create.call_args
        assert call_kwargs.kwargs["messages"] is messages


def test_together_infer_wraps_string_payload() -> None:
    """Non-list payload is wrapped in a single user message (backward-compat)."""
    mock_together_cls = MagicMock()
    client = MagicMock()
    mock_together_cls.return_value = client
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="ok"))]
    response.model_dump.return_value = {}
    client.chat.completions.create.return_value = response

    with patch.object(together_module, "Together", mock_together_cls):
        provider = TogetherAIProvider(api_key="k", default_model="m")
        provider.infer("m", "hello plain string")
        call_kwargs = client.chat.completions.create.call_args
        sent = call_kwargs.kwargs["messages"]
        assert sent == [{"role": "user", "content": "hello plain string"}]


def test_together_infer_stream_rejects_embeddings() -> None:
    mock_together_cls = MagicMock()
    client = MagicMock()
    mock_together_cls.return_value = client

    with patch.object(together_module, "Together", mock_together_cls):
        provider = TogetherAIProvider(api_key="k", default_model="m")
        with pytest.raises(TypeError):
            next(provider.infer_stream("m", ["x"], model_type="embedding"))


def _chat_provider() -> tuple[TogetherAIProvider, MagicMock]:
    mock_together_cls = MagicMock()
    client = MagicMock()
    mock_together_cls.return_value = client
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="ok"))]
    response.model_dump.return_value = {}
    client.chat.completions.create.return_value = response
    with patch.object(together_module, "Together", mock_together_cls):
        provider = TogetherAIProvider(api_key="k", default_model="m")
    return provider, client


def test_together_maps_sampling_and_output_params() -> None:
    provider, client = _chat_provider()
    params = {
        "temperature": 0.2,
        "top_p": 0.9,
        "max_tokens": 256,
        "response_format": {"type": "json_object"},
        "reasoning_effort": "medium",
    }

    provider.infer("m", "hello", params=params)

    sent = client.chat.completions.create.call_args.kwargs
    assert sent["temperature"] == 0.2
    assert sent["top_p"] == 0.9
    assert sent["max_tokens"] == 256
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["reasoning_effort"] == "medium"


def test_together_maps_reasoning_enabled_to_toggle() -> None:
    provider, client = _chat_provider()

    provider.infer("m", "hello", params={"reasoning_enabled": True})

    sent = client.chat.completions.create.call_args.kwargs
    assert sent["reasoning"] == {"enabled": True}
    assert "reasoning_enabled" not in sent


def test_together_spreads_extra_params() -> None:
    provider, client = _chat_provider()

    provider.infer("m", "hello", params={"extra": {"chat_template_kwargs": {"thinking": True}}})

    sent = client.chat.completions.create.call_args.kwargs
    assert sent["chat_template_kwargs"] == {"thinking": True}
    assert "extra" not in sent


def test_together_omits_unset_params() -> None:
    provider, client = _chat_provider()

    provider.infer("m", "hello")

    sent = client.chat.completions.create.call_args.kwargs
    assert set(sent) == {"model", "messages"}


def test_together_per_call_params_override_constructor_defaults() -> None:
    mock_together_cls = MagicMock()
    client = MagicMock()
    mock_together_cls.return_value = client
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="ok"))]
    response.model_dump.return_value = {}
    client.chat.completions.create.return_value = response

    with patch.object(together_module, "Together", mock_together_cls):
        provider = TogetherAIProvider(
            api_key="k",
            default_model="m",
            default_params={"temperature": 0.1, "max_tokens": 100},
        )
        provider.infer("m", "hello", params={"temperature": 0.9})

    sent = client.chat.completions.create.call_args.kwargs
    assert sent["temperature"] == 0.9
    assert sent["max_tokens"] == 100
