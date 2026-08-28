from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from aris.core.config import AppConfig
from aris.ui.hud_window import HudWindow


def main() -> int:
    """Xác nhận `Hey ARIS, dừng nhạc` dừng playback nhưng không đóng cửa sổ HUD."""
    application = QApplication.instance() or QApplication([])
    config = replace(
        AppConfig.load(),
        auto_listen=False,
        cloud_tts_enabled=False,
        hardware_enabled=False,
    )
    window = HudWindow(config)
    window.voice_output = False
    window.show()
    result = {"passed": False}

    def dispatch() -> None:
        """Tạo music context giả trong RAM rồi gửi transcript qua đúng wake pipeline."""
        window.startup_sequence.stop()
        window.music._current_title = "probe music"  # noqa: SLF001 - runtime probe
        window._on_transcript("Hey ARIS, dừng nhạc")  # noqa: SLF001 - runtime probe
        QTimer.singleShot(350, inspect)

    def inspect() -> None:
        """Kiểm tra playback được xóa trong khi HUD không bước vào shutdown."""
        result["passed"] = (
            window.isVisible()
            and not window.music.has_music_context
            and not window._shutting_down  # noqa: SLF001 - runtime probe
        )
        status = "ok" if result["passed"] else "failed"
        print(
            f"MUSIC_STOP_COMMAND_PROBE {status} "
            f"window_visible={str(window.isVisible()).lower()} "
            f"music_context={str(window.music.has_music_context).lower()} "
            f"shutting_down={str(window._shutting_down).lower()}"  # noqa: SLF001
        )
        window.close()
        application.quit()

    QTimer.singleShot(120, dispatch)
    QTimer.singleShot(5_000, application.quit)
    application.exec()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
