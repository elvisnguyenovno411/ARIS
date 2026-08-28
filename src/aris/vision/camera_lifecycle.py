from __future__ import annotations

import threading


class CameraLifecycle:
    """Theo dõi nhu cầu scan/gesture để camera chỉ chạy khi người dùng chủ động yêu cầu."""

    def __init__(self) -> None:
        """Khởi tạo trạng thái tắt hoàn toàn; constructor không được phép mở webcam."""
        self._scan_requested = threading.Event()
        self._gesture_enabled = threading.Event()

    @property
    def should_run(self) -> bool:
        """Cho biết scan hoặc gesture còn cần camera hoạt động hay không."""
        return self._scan_requested.is_set() or self._gesture_enabled.is_set()

    @property
    def scan_requested(self) -> bool:
        """Cho biết một lần quét tay đang chờ đủ landmark ổn định hay không."""
        return self._scan_requested.is_set()

    @property
    def gesture_enabled(self) -> bool:
        """Cho biết người dùng đang bật điều khiển gesture hay không."""
        return self._gesture_enabled.is_set()

    def request_scan(self) -> None:
        """Đánh dấu scan cần camera; caller chịu trách nhiệm khởi động worker thread."""
        self._scan_requested.set()

    def complete_scan(self) -> None:
        """Kết thúc nhu cầu scan nhưng giữ camera nếu gesture vẫn đang bật."""
        self._scan_requested.clear()

    def set_gesture_enabled(self, enabled: bool) -> None:
        """Bật hoặc tắt nhu cầu camera dành cho gesture theo hành động người dùng."""
        if enabled:
            self._gesture_enabled.set()
        else:
            self._gesture_enabled.clear()

    def clear(self) -> None:
        """Xóa mọi nhu cầu camera khi đóng app hoặc dừng controller cưỡng bức."""
        self._scan_requested.clear()
        self._gesture_enabled.clear()
