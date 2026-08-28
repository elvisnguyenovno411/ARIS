from __future__ import annotations

from PySide6.QtCore import QTimer

from aris.app import create_application


def main() -> int:
    """Kiểm tra chuỗi mở ba model, focus, zoom và đóng riêng trên HUD thật."""
    application, window = create_application()
    window.voice_output = False
    window.show()
    result = {"passed": False}

    def run_probe() -> None:
        """Gửi toàn bộ lệnh qua router và kiểm tra đúng model đang nhận điều khiển."""
        for key in ("rasengan", "minato_kunai", "iron_man_mask"):
            window._open_model(key)  # noqa: SLF001 - intentional QA hook
        window._dispatch_intent(  # noqa: SLF001 - intentional QA hook
            window.router.route("Chọn Rasengan")
        )
        rasengan = window.model_manager.active_view
        before = rasengan.target_camera_distance if rasengan is not None else 0.0
        window._dispatch_intent(  # noqa: SLF001 - intentional QA hook
            window.router.route("Phóng to model đang chọn 30%")
        )
        after = rasengan.target_camera_distance if rasengan is not None else before
        window._dispatch_intent(  # noqa: SLF001 - intentional QA hook
            window.router.route("Đóng Minato Kunai")
        )
        named_close_ok = window.model_manager.model_keys == (
            "rasengan",
            "iron_man_mask",
        )
        window._dispatch_intent(  # noqa: SLF001 - intentional QA hook
            window.router.route("Close")
        )
        result["passed"] = (
            named_close_ok
            and window.model_manager.active_key == "iron_man_mask"
            and window.model_manager.model_keys == ("iron_man_mask",)
            and after < before
        )
        status = "ok" if result["passed"] else "failed"
        print(
            f"MULTI_MODEL_PROBE {status} active={window.model_manager.active_key} "
            f"models={','.join(window.model_manager.model_keys)} "
            f"zoom_before={before:.3f} zoom_after={after:.3f}"
        )
        QTimer.singleShot(500, window.close)
        QTimer.singleShot(650, application.quit)

    QTimer.singleShot(500, run_probe)
    application.exec()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
