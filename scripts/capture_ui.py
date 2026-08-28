from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer

from aris.app import create_application


def main() -> int:
    """Mở ARIS ngắn, chụp cửa sổ để kiểm tra layout rồi tự thoát."""
    if len(sys.argv) not in {2, 3}:
        raise SystemExit("Usage: python scripts/capture_ui.py <output.png> [delay_ms]")
    output = Path(sys.argv[1]).resolve()
    delay_ms = int(sys.argv[2]) if len(sys.argv) == 3 else 2400
    output.parent.mkdir(parents=True, exist_ok=True)
    application, window = create_application()
    window.showMaximized()

    def capture() -> None:
        """Lưu ảnh widget đã render và đóng ứng dụng sau khi hoàn tất."""
        window.grab().save(str(output), "PNG")
        window.close()
        application.quit()

    QTimer.singleShot(max(250, delay_ms), capture)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
