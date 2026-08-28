from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from aris.core.config import AppConfig
from aris.search.client import ArisWebSearch, parse_web_search_response


def enabled_config(**overrides) -> AppConfig:
    """Tạo cấu hình Web Search giả đã opt-in mà không dùng key thật của máy."""
    values = {
        "openai_api_key": "test-key",
        "web_search_enabled": True,
        "web_search_request_limit": 20,
        "web_search_cache_seconds": 300,
    }
    values.update(overrides)
    return replace(AppConfig.load(), **values)


def fake_response() -> SimpleNamespace:
    """Tạo Responses payload giả gồm citation hợp lệ và URL nguy hiểm để kiểm tra lọc."""
    annotations = [
        SimpleNamespace(
            type="url_citation",
            title="OpenAI Documentation",
            url="https://developers.openai.com/api/docs",
        ),
        SimpleNamespace(
            type="url_citation",
            title="Unsafe",
            url="file:///C:/private.txt",
        ),
    ]
    message = SimpleNamespace(
        type="message",
        content=[
            SimpleNamespace(
                type="output_text",
                text="Đây là kết quả mới.",
                annotations=annotations,
            )
        ],
    )
    web_call = SimpleNamespace(
        type="web_search_call",
        action=SimpleNamespace(
            sources=[
                SimpleNamespace(
                    type="url",
                    title="Second source",
                    url="https://example.com/reference",
                )
            ]
        ),
    )
    return SimpleNamespace(output_text="Đây là kết quả mới.", output=[web_call, message])


def test_web_search_request_is_stateless_limited_and_uses_low_context() -> None:
    """Kiểm tra Web Search tắt lưu response, giảm context và không gửi dữ liệu thành tool khác."""
    captured: dict[str, object] = {}

    class _FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return fake_response()

    search = ArisWebSearch(enabled_config())
    search._client = SimpleNamespace(responses=_FakeResponses())

    result = search.search("robot mới nhất")

    assert result.success is True
    assert result.answer == "Đây là kết quả mới."
    assert captured["store"] is False
    assert captured["tools"] == [{"type": "web_search", "search_context_size": "low"}]
    assert captured["tool_choice"] == "required"
    assert captured["max_tool_calls"] == 1
    assert captured["include"] == ["web_search_call.action.sources"]
    assert captured["reasoning"] == {"effort": "none"}
    assert captured["text"] == {"verbosity": "low"}
    assert captured["max_output_tokens"] == 420
    assert search.requests_remaining == 19


def test_parser_keeps_only_public_http_sources_and_deduplicates() -> None:
    """Đảm bảo citation không thể mở file local, credential URL hoặc lặp cùng nguồn."""
    response = fake_response()
    response.output[0].action.sources.append(
        SimpleNamespace(
            type="url",
            title="Duplicate",
            url="https://developers.openai.com/api/docs",
        )
    )
    response.output[0].action.sources.append(
        SimpleNamespace(
            type="url",
            title="Credential URL",
            url="https://name:secret@example.com/private",
        )
    )

    answer, sources = parse_web_search_response(response)

    assert answer == "Đây là kết quả mới."
    assert {source.url for source in sources} == {
        "https://developers.openai.com/api/docs",
        "https://example.com/reference",
    }


def test_repeated_query_uses_ram_cache_without_second_api_call() -> None:
    """Kiểm tra cùng truy vấn trong năm phút không gọi API thêm lần nữa."""
    calls = 0

    class _FakeResponses:
        def create(self, **_kwargs):
            nonlocal calls
            calls += 1
            return fake_response()

    search = ArisWebSearch(enabled_config())
    search._client = SimpleNamespace(responses=_FakeResponses())

    first = search.search("AR glasses")
    second = search.search("AR glasses")

    assert first.cached is False
    assert second.cached is True
    assert calls == 1
    assert search.requests_remaining == 19


def test_session_limit_blocks_network_before_an_extra_paid_request() -> None:
    """Đảm bảo hết giới hạn phiên sẽ trả fallback trước khi tạo thêm API request."""
    calls = 0

    class _FakeResponses:
        def create(self, **_kwargs):
            nonlocal calls
            calls += 1
            return fake_response()

    search = ArisWebSearch(
        enabled_config(web_search_request_limit=1, web_search_cache_seconds=0)
    )
    search._client = SimpleNamespace(responses=_FakeResponses())

    assert search.search("first query").success is True
    blocked = search.search("second query")

    assert blocked.success is False
    assert blocked.error_code == "session_limit"
    assert calls == 1


def test_runtime_guard_blocks_web_search_without_removing_key() -> None:
    """Đảm bảo sonar ALERT khóa tra cứu nhưng không xóa khóa OpenAI trong cấu hình."""
    search = ArisWebSearch(enabled_config())

    search.set_runtime_enabled(False)
    result = search.search("should not leave this process")

    assert search.api_enabled is False
    assert result.error_code == "not_configured"
    assert search.config.openai_api_key == "test-key"
