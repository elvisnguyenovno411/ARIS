from __future__ import annotations

import sys
import time

from PySide6.QtCore import QTimer

from aris.app import create_application


def run_probe(model_key: str = "rasengan", sample_ms: int = 3500) -> int:
    """Đo frame OpenGL thực tế khi model và camera chạy mà không lưu camera frame."""
    application, window = create_application()
    measurement = {"frames": 0, "started": 0.0, "connected": False}

    def count_frame() -> None:
        """Đếm frame swap chỉ trong khoảng đo sau khi OpenGL đã warm-up."""
        if measurement["started"]:
            measurement["frames"] += 1

    def begin_sample() -> None:
        """Bỏ qua giai đoạn mở webcam/model rồi bắt đầu phép đo ổn định."""
        view = window.model_manager.active_view
        if view is not None and not measurement["connected"]:
            view.frameSwapped.connect(count_frame)
            measurement["connected"] = True
        measurement["frames"] = 0
        measurement["started"] = time.perf_counter()

    def finish_sample() -> None:
        """In FPS trung bình và giải phóng camera, microphone cùng cửa sổ."""
        elapsed = max(0.001, time.perf_counter() - measurement["started"])
        fps = measurement["frames"] / elapsed
        print(
            f"FPS_PROBE model={model_key} render_fps={fps:.1f} "
            "camera_frames_saved=false"
        )
        window.close()
        application.quit()

    window.show()
    startup_ready_ms = 4700
    sample_start_ms = startup_ready_ms + 900
    QTimer.singleShot(
        startup_ready_ms,
        lambda: window._open_model(model_key),  # noqa: SLF001
    )
    QTimer.singleShot(sample_start_ms, begin_sample)
    QTimer.singleShot(sample_start_ms + max(1500, int(sample_ms)), finish_sample)
    return application.exec()


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "rasengan"
    raise SystemExit(run_probe(key))
