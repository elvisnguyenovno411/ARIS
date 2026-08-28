from __future__ import annotations

from aris.ui.typewriter_label import TypewriterLabel


def test_typewriter_reveals_the_complete_message(qtbot) -> None:
    """Kiểm tra hiệu ứng gõ luôn kết thúc bằng đúng nội dung không có con trỏ."""
    label = TypewriterLabel()
    qtbot.addWidget(label)

    label.show_typed("ARIS online", 1000)

    qtbot.waitUntil(lambda: label.text() == "ARIS online", timeout=2000)


def test_typewriter_empty_message_stays_hidden(qtbot) -> None:
    """Kiểm tra message rỗng không để lại con trỏ hoặc label thừa trên HUD."""
    label = TypewriterLabel()
    qtbot.addWidget(label)

    label.show_typed("   ")

    assert label.text() == ""
    assert label.isHidden()


def test_typewriter_can_follow_a_longer_speech_duration(qtbot) -> None:
    """Kiểm tra text chưa chạy trước audio khi HUD truyền thời lượng câu nói thật."""
    label = TypewriterLabel()
    qtbot.addWidget(label)
    message = "ARIS đang đồng bộ hiệu ứng chữ với giọng nói."

    label.show_typed(message, 1000, typing_duration_ms=600)

    qtbot.wait(140)
    assert label.text() != message
    qtbot.waitUntil(lambda: label.text() == message, timeout=1200)
