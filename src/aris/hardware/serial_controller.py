from __future__ import annotations

import queue
import threading
from collections.abc import Iterable

from PySide6.QtCore import QObject, Signal

from aris.hardware.protocol import (
    GuardState,
    HardwareEventType,
    normalize_hardware_command,
    parse_hardware_line,
)


class HardwareController(QObject):
    """Đọc Arduino ở worker thread và chỉ gửi các lệnh guard nằm trong allowlist."""

    connection_changed = Signal(bool, str)
    state_changed = Signal(str)
    distance_changed = Signal(float)
    remote_received = Signal(str)
    status_changed = Signal(str, str)

    def __init__(
        self,
        enabled: bool = True,
        configured_port: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Lưu lựa chọn phần cứng; chưa mở COM cho tới khi gọi start."""
        super().__init__(parent)
        self.enabled = bool(enabled)
        self.configured_port = configured_port
        self._commands: queue.Queue[str] = queue.Queue(maxsize=16)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = False
        self._connection_lock = threading.Lock()
        self._last_state: GuardState | None = None

    @property
    def is_connected(self) -> bool:
        """Cho biết worker hiện có đang giữ một kết nối Serial hợp lệ hay không."""
        with self._connection_lock:
            return self._connected

    def start(self) -> None:
        """Khởi động worker tự dò Arduino mà không chặn event loop của Qt."""
        if not self.enabled or (self._thread is not None and self._thread.is_alive()):
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="aris-hardware",
            daemon=True,
        )
        self._thread.start()

    def send_command(self, command: str) -> bool:
        """Xếp một lệnh guard hợp lệ; trả False nếu offline hoặc ngoài allowlist."""
        normalized = normalize_hardware_command(command)
        if normalized is None or not self.is_connected:
            return False
        try:
            self._commands.put_nowait(normalized)
        except queue.Full:
            return False
        return True

    def stop(self) -> None:
        """Yêu cầu worker đóng COM và chờ ngắn để app thoát sạch trên Windows."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.5)
        self._thread = None
        self._set_connected(False, "")

    def _run(self) -> None:
        """Duy trì vòng kết nối lại Arduino cho tới khi ứng dụng yêu cầu dừng."""
        while not self._stop_event.is_set():
            port = self._choose_port()
            if port is None:
                self._set_connected(False, "")
                self._stop_event.wait(2.0)
                continue
            try:
                self._read_port(port)
            except Exception as error:
                self.status_changed.emit(
                    f"Arduino unavailable: {type(error).__name__}.",
                    "warning",
                )
            finally:
                self._last_state = None
                self._set_connected(False, port)
            self._stop_event.wait(1.4)

    def _choose_port(self) -> str | None:
        """Ưu tiên cổng cấu hình rồi tự dò các USB VID hoặc mô tả Arduino phổ biến."""
        if self.configured_port:
            return self.configured_port
        try:
            from serial.tools import list_ports

            ports: Iterable[object] = list_ports.comports()
            for port in ports:
                description = str(getattr(port, "description", "")).casefold()
                vendor_id = getattr(port, "vid", None)
                if "arduino" in description or vendor_id in {0x2341, 0x2A03, 0x1A86}:
                    return str(port.device)
        except Exception:
            return None
        return None

    def _read_port(self, port: str) -> None:
        """Mở một cổng Serial, gửi STATUS và chuyển từng dòng thành sự kiện có kiểu."""
        import serial

        with serial.Serial(port, 115200, timeout=0.2, write_timeout=1.0) as connection:
            if self._stop_event.wait(2.1):
                return
            connection.reset_input_buffer()
            connection.write(b"STATUS\n")
            self._set_connected(True, port)
            self.status_changed.emit(f"Arduino guard connected: {port}", "ready")
            while not self._stop_event.is_set():
                self._flush_commands(connection)
                payload = connection.readline()
                if not payload:
                    continue
                line = payload.decode("ascii", errors="ignore")
                self._handle_line(line)

    def _flush_commands(self, connection: object) -> None:
        """Gửi hết lệnh guard đã kiểm tra trong hàng đợi sang Arduino."""
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            connection.write(f"{command}\n".encode("ascii"))

    def _handle_line(self, line: str) -> None:
        """Bỏ qua dòng lạ và phát signal Qt tương ứng cho sự kiện phần cứng hợp lệ."""
        event = parse_hardware_line(line)
        if event is None:
            return
        if event.kind is HardwareEventType.STATE:
            state = GuardState(event.value)
            if state is not self._last_state:
                self._last_state = state
                self.state_changed.emit(state.value)
        elif event.kind is HardwareEventType.DISTANCE_CM:
            self.distance_changed.emit(float(event.value))
        elif event.kind is HardwareEventType.REMOTE:
            self.remote_received.emit(event.value)

    def _set_connected(self, connected: bool, port: str) -> None:
        """Cập nhật trạng thái kết nối thread-safe và chỉ phát signal khi có thay đổi."""
        with self._connection_lock:
            changed = connected != self._connected
            self._connected = connected
        if changed:
            self.connection_changed.emit(connected, port)
