from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QPoint, QTimer

from aris.app import create_application
from aris.core.config import AppConfig


def main() -> int:
    """Mở một hoặc nhiều model nổi, chụp HUD để QA rồi tự đóng ứng dụng."""
    if len(sys.argv) not in {3, 4}:
        raise SystemExit(
            "Usage: python scripts/capture_hologram.py "
            "<model-key[,model-key...]> <output.png> [open_delay_ms]"
        )
    model_keys = tuple(key.strip() for key in sys.argv[1].split(",") if key.strip())
    output = Path(sys.argv[2]).resolve()
    open_delay_ms = int(sys.argv[3]) if len(sys.argv) == 4 else 4700
    output.parent.mkdir(parents=True, exist_ok=True)
    capture_config = replace(
        AppConfig.load(),
        openai_api_key=None,
        web_search_enabled=False,
        cloud_tts_enabled=False,
        youtube_music_enabled=False,
        auto_listen=False,
        hardware_enabled=False,
    )
    application, window = create_application(capture_config)
    window.showMaximized()

    def open_model() -> None:
        """Gọi từng model qua API nội bộ để test đúng lớp hologram nổi thật."""
        for model_key in model_keys:
            window._open_model(model_key)  # noqa: SLF001 - intentional visual QA hook
        widgets = [
            window.model_manager._widgets[key]  # noqa: SLF001 - intentional visual QA hook
            for key in model_keys
            if key in window.model_manager._widgets  # noqa: SLF001
        ]
        if len(widgets) > 1:
            available_width = window.hud_page.width()
            margin = 42
            step = max(1, (available_width - 2 * margin) // (len(widgets) - 1))
            for index, widget in enumerate(widgets):
                center_x = margin + index * step
                widget.move_clamped(
                    QPoint(center_x - widget.width() // 2, window.hud_page.height() // 7)
                )

    def capture() -> None:
        """Chụp qua compositor thật để phát hiện nền đen của QOpenGLWidget trên Windows."""
        screen = window.screen()
        if screen is None:
            raise RuntimeError("No screen is available for visual QA.")
        screen.grabWindow(int(window.winId())).save(str(output), "PNG")
        window.close()
        application.quit()

    QTimer.singleShot(max(250, open_delay_ms), open_model)
    QTimer.singleShot(max(250, open_delay_ms) + 2700, capture)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
