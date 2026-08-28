from aris.ai.language import detect_language


def test_detects_vietnamese_with_and_without_diacritics() -> None:
    """Kiểm tra câu Việt có dấu hoặc không dấu đều chọn giọng/phản hồi tiếng Việt."""
    assert detect_language("Bạn mở Chrome giúp mình nhé", "en") == "vi"
    assert detect_language("mo chrome va giam am luong", "en") == "vi"


def test_detects_natural_english_commands() -> None:
    """Kiểm tra câu lệnh tiếng Anh không bị ngôn ngữ giao diện Việt ghi đè."""
    assert detect_language("Could you please open Chrome?", "vi") == "en"
    assert detect_language("Lower the volume and play music", "vi") == "en"


def test_ambiguous_phrase_uses_configured_default() -> None:
    """Kiểm tra tên riêng không đủ dữ kiện sẽ dùng ngôn ngữ HUD hiện tại."""
    assert detect_language("Rasengan", "vi") == "vi"
    assert detect_language("Rasengan", "en") == "en"
