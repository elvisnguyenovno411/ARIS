from __future__ import annotations

import json
import os
import threading
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_STATE: dict[str, Any] = {
    "schema_version": 1,
    "settings": {
        "language": "en",
        "voice_output": True,
        "gesture_control": False,
        "music_volume": 72,
    },
    "selected_model": "rasengan",
    "hand_scan": None,
    "recent_actions": [],
}

SAVE_RETRY_DELAYS = (0.01, 0.02, 0.04, 0.08, 0.12)


class JsonStore:
    """Lưu trạng thái ARIS vào JSON bằng ghi nguyên tử để tránh hỏng dữ liệu."""

    def __init__(self, path: Path, max_actions: int = 30) -> None:
        """Khởi tạo kho dữ liệu với đường dẫn và giới hạn lịch sử hành động."""
        self.path = path
        self.max_actions = max_actions
        self._lock = threading.RLock()
        self._pending_state: dict[str, Any] | None = None
        self._last_save_error: OSError | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def persistence_pending(self) -> bool:
        """Cho biết trạng thái mới đang chờ ghi lại vì file tạm thời bị Windows khóa."""
        with self._lock:
            return self._pending_state is not None

    def load(self) -> dict[str, Any]:
        """Đọc trạng thái; trả về mặc định an toàn nếu file thiếu hoặc bị lỗi."""
        with self._lock:
            if self._pending_state is not None:
                return deepcopy(self._pending_state)
            if not self.path.exists():
                return deepcopy(DEFAULT_STATE)
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return deepcopy(DEFAULT_STATE)
            if not isinstance(payload, dict):
                return deepcopy(DEFAULT_STATE)
            state = deepcopy(DEFAULT_STATE)
            state.update(payload)
            if isinstance(payload.get("settings"), dict):
                state["settings"].update(payload["settings"])
            return state

    def save(self, state: dict[str, Any]) -> None:
        """Ghi JSON nguyên tử, retry khóa OneDrive và giữ bản RAM nếu chưa thể lưu."""
        with self._lock:
            serialized = json.dumps(state, ensure_ascii=False, indent=2)
            self._pending_state = deepcopy(state)
            temporary = self.path.with_name(
                f".{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            try:
                temporary.write_text(serialized, encoding="utf-8")
                for attempt in range(len(SAVE_RETRY_DELAYS) + 1):
                    try:
                        os.replace(temporary, self.path)
                    except PermissionError as error:
                        self._last_save_error = error
                        if attempt >= len(SAVE_RETRY_DELAYS):
                            break
                        time.sleep(SAVE_RETRY_DELAYS[attempt])
                    else:
                        self._pending_state = None
                        self._last_save_error = None
                        break
            except OSError as error:
                # Trạng thái phụ không được phép làm gián đoạn luồng hội thoại chính.
                self._last_save_error = error
            finally:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def update(self, **changes: Any) -> dict[str, Any]:
        """Cập nhật các khóa cấp cao nhất và trả về bản trạng thái mới."""
        with self._lock:
            state = self.load()
            state.update(changes)
            self.save(state)
            return deepcopy(state)

    def update_settings(self, **changes: Any) -> dict[str, Any]:
        """Cập nhật tùy chọn giao diện mà không ghi đè các cài đặt khác."""
        with self._lock:
            state = self.load()
            state["settings"].update(changes)
            self.save(state)
            return deepcopy(state)

    def append_action(self, action: str, success: bool, message: str) -> None:
        """Thêm một mục lịch sử đã rút gọn và giới hạn tổng số mục lưu local."""
        with self._lock:
            state = self.load()
            state["recent_actions"].append(
                {
                    "action": action,
                    "success": success,
                    "message": message[:240],
                    "created_at": datetime.now(UTC).isoformat(),
                }
            )
            state["recent_actions"] = state["recent_actions"][-self.max_actions :]
            self.save(state)

    def clear_history(self) -> dict[str, Any]:
        """Xóa lịch sử hành động và dữ liệu quét nhưng giữ cài đặt người dùng."""
        with self._lock:
            state = self.load()
            state["recent_actions"] = []
            state["hand_scan"] = None
            self.save(state)
            return deepcopy(state)
