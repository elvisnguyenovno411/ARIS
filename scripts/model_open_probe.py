from __future__ import annotations

import sys
import time

from PySide6.QtCore import QEvent, QObject, QTimer

from aris.app import create_application


class WindowVisibilityProbe(QObject):
    """Đếm sự kiện ẩn của cửa sổ chính trong đúng khoảng mở model đầu tiên."""

    def __init__(self) -> None:
        """Khởi tạo bộ đếm ở trạng thái chưa theo dõi."""
        super().__init__()
        self.tracking = False
        self.hide_events = 0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Ghi nhận Hide event nhưng không chặn Qt tiếp tục xử lý cửa sổ."""
        del watched
        if self.tracking and event.type() is QEvent.Type.Hide:
            self.hide_events += 1
        return False


def main() -> int:
    """Đo lần mở model đầu và thất bại nếu cửa sổ ARIS từng bị ẩn."""
    model_key = sys.argv[1] if len(sys.argv) > 1 else "spider_man_mask"
    application, window = create_application()
    probe = WindowVisibilityProbe()
    window.installEventFilter(probe)
    window.show()
    result = {"passed": False, "elapsed_ms": 0.0}

    def open_first_model() -> None:
        """Bật theo dõi ngay trước lệnh mở để loại sự kiện startup khỏi kết quả."""
        probe.tracking = True
        started_at = time.perf_counter()
        window._open_model(model_key)  # noqa: SLF001 - intentional runtime probe
        result["elapsed_ms"] = (time.perf_counter() - started_at) * 1000.0
        QTimer.singleShot(900, finish_probe)

    def finish_probe() -> None:
        """In kết quả rồi đóng tài nguyên sau khi compositor có thời gian ổn định."""
        probe.tracking = False
        result["passed"] = (
            window.isVisible()
            and probe.hide_events == 0
            and window.model_manager.active_key == model_key
        )
        status = "ok" if result["passed"] else "failed"
        print(
            f"MODEL_OPEN_PROBE {status} model={model_key} "
            f"elapsed_ms={result['elapsed_ms']:.1f} hide_events={probe.hide_events} "
            f"window_visible={window.isVisible()}"
        )
        window.close()
        application.quit()

    QTimer.singleShot(4700, open_first_model)
    application.exec()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
