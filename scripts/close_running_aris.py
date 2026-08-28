from __future__ import annotations

import ctypes
from ctypes import wintypes

WM_CLOSE = 0x0010


def main() -> int:
    """Gửi WM_CLOSE đến cửa sổ ARIS đang chạy để giải phóng thiết bị trước khi test."""
    user32 = ctypes.windll.user32
    closed = 0
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def visit_window(hwnd: int, _lparam: int) -> bool:
        """Chỉ đóng cửa sổ có title chính xác của ARIS, không đụng ứng dụng khác."""
        nonlocal closed
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, len(title))
        if title.value.startswith("ARIS — Augmented Reality Intelligence System"):
            closed += int(bool(user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)))
        return True

    user32.EnumWindows(callback_type(visit_window), 0)
    print(f"CLOSE_RUNNING_ARIS windows={closed}")
    return 0 if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
