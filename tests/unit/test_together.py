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


def test_together_infer_stream_rejects_embeddings() -> None:
    mock_together_cls = MagicMock()
    client = MagicMock()
    mock_together_cls.return_value = client

    with patch.object(together_module, "Together", mock_together_cls):
        provider = TogetherAIProvider(api_key="k", default_model="m")
        with pytest.raises(TypeError):
            next(provider.infer_stream("m", ["x"], model_type="embedding"))
