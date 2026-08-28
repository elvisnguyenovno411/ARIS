from __future__ import annotations

import time
from dataclasses import replace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from aris.core.config import AppConfig
from aris.core.types import IntentType
from aris.ui.hud_window import HudWindow


def main() -> int:
    """Gửi lệnh tắt qua router thật và xác nhận HUD đóng sau hiệu ứng power-down."""
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
    state = {"closed": False, "started": 0.0}

    def dispatch_shutdown() -> None:
        """Giả lập nhạc đang có context rồi phát câu đóng ARIS trực tiếp."""
        window.startup_sequence.stop()
        window.music._current_title = "probe music"  # noqa: SLF001 - runtime probe
        intent = window.router.route("Đóng ARIS", music_context=True)
        if intent.kind is not IntentType.EXIT_ARIS:
            print(f"SHUTDOWN_COMMAND_PROBE failed intent={intent.kind.value}")
            application.exit(2)
            return
        state["started"] = time.perf_counter()
        window._dispatch_intent(intent)  # noqa: SLF001 - intentional runtime probe

    def report_closed() -> None:
        """Đánh dấu cửa sổ đã biến mất trước watchdog năm giây."""
        state["closed"] = True
        elapsed_ms = (time.perf_counter() - state["started"]) * 1000.0
        print(f"SHUTDOWN_COMMAND_PROBE ok elapsed_ms={elapsed_ms:.1f}")
        application.quit()

    def timeout() -> None:
        """Kết thúc probe nếu lệnh đã nhận nhưng cửa sổ không đóng."""
        if not state["closed"]:
            print("SHUTDOWN_COMMAND_PROBE failed reason=window_still_visible")
            window.close()
            application.exit(1)

    application.lastWindowClosed.connect(report_closed)
    QTimer.singleShot(150, dispatch_shutdown)
    QTimer.singleShot(5_000, timeout)
    code = application.exec()
    return 0 if state["closed"] else code or 1


if __name__ == "__main__":
    raise SystemExit(main())
