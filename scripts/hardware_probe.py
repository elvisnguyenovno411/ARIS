from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QTimer

from aris.hardware.serial_controller import HardwareController


def main() -> int:
    """Kiểm tra auto-detect, STATUS và event thật mà không khởi động toàn bộ HUD."""
    application = QCoreApplication.instance() or QCoreApplication([])
    controller = HardwareController(enabled=True)
    result = {"connected": False, "state": False}

    def report_connection(connected: bool, port: str) -> None:
        """Ghi nhận kết nối thật để probe không pass khi máy không có cổng COM."""
        result["connected"] = result["connected"] or connected
        print(f"HARDWARE_PROBE connected={connected} port={port}")

    def report_state(state: str) -> None:
        """Ghi nhận phản hồi STATUS hợp lệ từ firmware thay vì chỉ mở được serial."""
        result["state"] = True
        print(f"HARDWARE_PROBE state={state}")

    controller.connection_changed.connect(report_connection)
    controller.state_changed.connect(report_state)
    controller.status_changed.connect(
        lambda message, state: print(f"HARDWARE_PROBE {state}={message}")
    )

    def request_status(connected: bool, _port: str) -> None:
        """Yêu cầu state sau khi COM sẵn sàng để xác nhận kênh gửi hai chiều."""
        if connected:
            controller.send_command("STATUS")

    controller.connection_changed.connect(request_status)
    controller.start()
    QTimer.singleShot(6500, application.quit)
    try:
        application.exec()
    finally:
        controller.stop()
    if not result["connected"]:
        print("HARDWARE_PROBE failed reason=no_arduino_port")
        return 1
    if not result["state"]:
        print("HARDWARE_PROBE failed reason=no_status_event")
        return 2
    print("HARDWARE_PROBE ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
