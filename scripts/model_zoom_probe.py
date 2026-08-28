from __future__ import annotations

from PySide6.QtCore import QTimer

from aris.app import create_application


def main() -> int:
    """Mở Rasengan, gửi lệnh zoom local và xác nhận camera distance thực sự giảm."""
    application, window = create_application()
    window.voice_output = False
    window.show()
    result = {"passed": False}

    def run_probe() -> None:
        """Gửi lệnh qua đúng router/HUD đang dùng trong app và so sánh target trước-sau."""
        window._open_model("rasengan")  # noqa: SLF001 - intentional QA hook
        view = window.model_manager.active_view
        if view is None:
            print("MODEL_ZOOM_PROBE failed reason=no_active_view")
            window.close()
            application.quit()
            return
        before = view.target_camera_distance
        intent = window.router.route("Phóng to Rasengan 30%")
        window._dispatch_intent(intent)  # noqa: SLF001 - intentional QA hook
        after = view.target_camera_distance
        result["passed"] = after < before
        status = "ok" if result["passed"] else "failed"
        print(f"MODEL_ZOOM_PROBE {status} before={before:.3f} after={after:.3f}")
        QTimer.singleShot(500, window.close)
        QTimer.singleShot(650, application.quit)

    QTimer.singleShot(500, run_probe)
    application.exec()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
