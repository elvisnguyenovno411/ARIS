from __future__ import annotations

import pytest

import aris.core.config as config_module


@pytest.fixture(autouse=True)
def prevent_real_cloud_calls(monkeypatch) -> None:
    """Khóa API thật trong mọi test, kể cả khi máy phát triển có `.env` chứa key."""
    monkeypatch.setattr(config_module, "load_dotenv", lambda *_args, **_kwargs: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ARIS_ENABLE_OPENAI", "false")
    monkeypatch.setenv("ARIS_ENABLE_CLOUD_TTS", "false")
    monkeypatch.setenv("ARIS_ENABLE_WEB_SEARCH", "false")
