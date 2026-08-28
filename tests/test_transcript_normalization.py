from __future__ import annotations

from aris.voice.transcript_normalization import normalize_voice_command


def test_exact_acoustic_alias_selects_rasengan() -> None:
    """Đảm bảo alias âm gần độc lập vẫn tạo đúng câu lệnh Rasengan."""
    assert normalize_voice_command("Racing game.") == "Hiển thị Rasengan"


def test_acoustic_alias_does_not_rewrite_a_search_query() -> None:
    """Đảm bảo yêu cầu tìm game đua xe không bị biến thành lệnh mở model."""
    command = "search racing game"

    assert normalize_voice_command(command) == command


def test_close_rasengan_repairs_mixed_language_acoustic_alias() -> None:
    """Đảm bảo tên Rasengan nghe sai trong câu đóng vẫn trở thành lệnh local an toàn."""
    commands = (
        "Close racing game.",
        "Closer raising gun",
        "Tắt ra sen gan!",
        "Tách ra sin gan",
    )

    for command in commands:
        assert normalize_voice_command(command) == "Close Rasengan"


def test_bare_close_and_misheard_aris_shutdown_are_repaired() -> None:
    """Kiểm tra STT nghe lệch `close` hoặc tên ARIS vẫn tạo câu local rõ nghĩa."""
    for transcript in ("Closed", "Clothes", "Clause", "Closing"):
        assert normalize_voice_command(transcript) == "Close"

    for transcript in ("Close Iris", "Đóng Eris", "Stop Ares", "Tắt Ari"):
        assert normalize_voice_command(transcript) == "Tắt ARIS"
