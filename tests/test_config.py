from __future__ import annotations

from aris.core.config import AppConfig


def test_openai_stays_disabled_without_explicit_opt_in(monkeypatch) -> None:
    """Đảm bảo key có sẵn trong máy không tự động kích hoạt dịch vụ cloud."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-must-not-be-used")
    monkeypatch.setenv("ARIS_ENABLE_OPENAI", "false")

    config = AppConfig.load()

    assert config.api_enabled is False
    assert config.openai_api_key is None


def test_openai_is_enabled_only_after_explicit_opt_in(monkeypatch) -> None:
    """Đảm bảo ARIS chỉ dùng API sau khi người dùng bật cờ đồng ý rõ ràng."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ARIS_ENABLE_OPENAI", "true")

    config = AppConfig.load()

    assert config.api_enabled is True
    assert config.openai_api_key == "test-key"


def test_web_search_requires_openai_and_a_separate_cost_opt_in(monkeypatch) -> None:
    """Đảm bảo có key vẫn chưa đủ; Web Search cần công tắc chi phí riêng của chủ dự án."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ARIS_ENABLE_OPENAI", "true")
    monkeypatch.setenv("ARIS_ENABLE_WEB_SEARCH", "false")
    assert AppConfig.load().web_search_enabled is False

    monkeypatch.setenv("ARIS_ENABLE_WEB_SEARCH", "true")
    assert AppConfig.load().web_search_enabled is True


def test_web_search_limits_are_clamped(monkeypatch) -> None:
    """Đảm bảo cấu hình sai không thể tạo phiên tra cứu không giới hạn hoặc cache quá dài."""
    monkeypatch.setenv("ARIS_WEB_SEARCH_SESSION_LIMIT", "999")
    monkeypatch.setenv("ARIS_WEB_SEARCH_CACHE_SECONDS", "99999")

    config = AppConfig.load()

    assert config.web_search_request_limit == 100
    assert config.web_search_cache_seconds == 3600


def test_cloud_tts_stays_off_when_only_transcription_is_enabled(monkeypatch) -> None:
    """Đảm bảo bật OpenAI không tự phát sinh thêm chi phí giọng đọc cloud."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ARIS_ENABLE_OPENAI", "true")
    monkeypatch.delenv("ARIS_ENABLE_CLOUD_TTS", raising=False)

    assert AppConfig.load().cloud_tts_enabled is False


def test_cloud_tts_requires_api_and_its_own_opt_in(monkeypatch) -> None:
    """Đảm bảo cloud TTS chỉ bật khi cả API lẫn công tắc TTS đều được đồng ý."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ARIS_ENABLE_CLOUD_TTS", "true")
    monkeypatch.setenv("ARIS_ENABLE_OPENAI", "false")
    assert AppConfig.load().cloud_tts_enabled is False

    monkeypatch.setenv("ARIS_ENABLE_OPENAI", "true")
    assert AppConfig.load().cloud_tts_enabled is True


def test_cinematic_tts_defaults_use_the_quality_voice(monkeypatch) -> None:
    """Đảm bảo cấu hình TTS dùng model điều khiển phong cách và giọng nữ Marin."""
    monkeypatch.delenv("ARIS_TTS_MODEL", raising=False)
    monkeypatch.delenv("ARIS_TTS_VOICE", raising=False)

    config = AppConfig.load()

    assert config.tts_model == "gpt-4o-mini-tts"
    assert config.tts_voice == "marin"
    assert "low-pitched" in config.tts_instructions


def test_spatial_is_the_default_gesture_mode(monkeypatch) -> None:
    """Đảm bảo tay mở MOVE và pinch TRANSFORM là cơ chế mặc định mới."""
    monkeypatch.delenv("ARIS_GESTURE_MODE", raising=False)

    config = AppConfig.load()

    assert config.gesture_mode == "spatial"


def test_grab_throw_mode_remains_available(monkeypatch) -> None:
    """Đảm bảo cơ chế grab-throw cũ vẫn tồn tại như fallback có chủ đích."""
    monkeypatch.setenv("ARIS_GESTURE_MODE", "grab_throw")

    assert AppConfig.load().gesture_mode == "grab_throw"


def test_legacy_gesture_mode_remains_available(monkeypatch) -> None:
    """Đảm bảo cơ chế gesture cũ vẫn có thể bật lại bằng cấu hình local an toàn."""
    monkeypatch.setenv("ARIS_GESTURE_MODE", "legacy")

    config = AppConfig.load()

    assert config.gesture_mode == "legacy"


def test_performance_defaults_balance_rendering_and_vision(monkeypatch) -> None:
    """Kiểm tra profile đo thực tế ưu tiên 60 FPS và inference 480×360 nhẹ hơn."""
    for name in (
        "ARIS_RENDER_FPS",
        "ARIS_VISION_FPS",
        "ARIS_VISION_WIDTH",
        "ARIS_VISION_HEIGHT",
    ):
        monkeypatch.delenv(name, raising=False)

    config = AppConfig.load()

    assert config.render_fps == 60
    assert config.vision_fps == 24
    assert (config.vision_width, config.vision_height) == (480, 360)


def test_performance_overrides_are_clamped(monkeypatch) -> None:
    """Kiểm tra cấu hình sai không thể tạo timer quá nhanh hoặc ảnh suy luận quá lớn."""
    monkeypatch.setenv("ARIS_RENDER_FPS", "999")
    monkeypatch.setenv("ARIS_VISION_FPS", "1")
    monkeypatch.setenv("ARIS_VISION_WIDTH", "invalid")
    monkeypatch.setenv("ARIS_VISION_HEIGHT", "9999")

    config = AppConfig.load()

    assert config.render_fps == 120
    assert config.vision_fps == 12
    assert config.vision_width == 480
    assert config.vision_height == 480


def test_auto_listen_is_enabled_by_default_and_can_be_disabled(monkeypatch) -> None:
    """Kiểm tra VAD tự động là mặc định nhưng vẫn có override manual-only an toàn."""
    monkeypatch.delenv("ARIS_AUTO_LISTEN", raising=False)
    assert AppConfig.load().auto_listen is True

    monkeypatch.setenv("ARIS_AUTO_LISTEN", "false")
    assert AppConfig.load().auto_listen is False


def test_transcription_language_automatically_detects_by_default(monkeypatch) -> None:
    """Đảm bảo phiên âm mặc định tự nhận Việt/Anh dù giao diện đang dùng tiếng Việt."""
    monkeypatch.setenv("ARIS_LANGUAGE", "vi")
    monkeypatch.delenv("ARIS_TRANSCRIPTION_LANGUAGE", raising=False)

    assert AppConfig.load().transcription_language is None


def test_transcription_language_can_use_automatic_detection(monkeypatch) -> None:
    """Đảm bảo người dùng song ngữ có thể yêu cầu API tự nhận diện ngôn ngữ."""
    monkeypatch.setenv("ARIS_LANGUAGE", "vi")
    monkeypatch.setenv("ARIS_TRANSCRIPTION_LANGUAGE", "auto")

    assert AppConfig.load().transcription_language is None


def test_hardware_is_opt_in_and_keeps_an_explicit_port(monkeypatch) -> None:
    """Kiểm tra bản public không tự mở COM nhưng vẫn giữ cổng do người dùng cấu hình."""
    monkeypatch.delenv("ARIS_ENABLE_HARDWARE", raising=False)
    monkeypatch.delenv("ARIS_HARDWARE_PORT", raising=False)
    config = AppConfig.load()
    assert config.hardware_enabled is False
    assert config.hardware_port is None

    monkeypatch.setenv("ARIS_ENABLE_HARDWARE", "false")
    monkeypatch.setenv("ARIS_HARDWARE_PORT", "COM7")
    config = AppConfig.load()
    assert config.hardware_enabled is False
    assert config.hardware_port == "COM7"
