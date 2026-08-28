import os
from pathlib import Path

from aris.storage.json_store import JsonStore


def test_store_round_trip_and_clear(tmp_path: Path) -> None:
    """Kiểm tra JSON lưu cài đặt và xóa lịch sử mà không mất tùy chọn."""
    store = JsonStore(tmp_path / "state.json")
    store.update_settings(language="vi")
    store.update(hand_scan={"handedness": "Left"})
    store.append_action("scan", True, "done")
    state = store.load()
    assert state["settings"]["language"] == "vi"
    assert state["hand_scan"]["handedness"] == "Left"
    cleared = store.clear_history()
    assert cleared["settings"]["language"] == "vi"
    assert cleared["hand_scan"] is None
    assert cleared["recent_actions"] == []


def test_store_retries_a_temporary_windows_file_lock(tmp_path, monkeypatch) -> None:
    """Kiểm tra khóa file ngắn của OneDrive được retry mà không mất trạng thái."""
    store = JsonStore(tmp_path / "state.json")
    real_replace = os.replace
    attempts = 0

    def replace_after_two_locks(source, destination) -> None:
        """Giả lập OneDrive khóa file hai nhịp trước khi cho phép replace."""
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("temporary OneDrive lock")
        real_replace(source, destination)

    monkeypatch.setattr("aris.storage.json_store.os.replace", replace_after_two_locks)
    monkeypatch.setattr("aris.storage.json_store.time.sleep", lambda _seconds: None)

    store.update(selected_model="minato_kunai")

    assert attempts == 3
    assert not store.persistence_pending
    assert store.load()["selected_model"] == "minato_kunai"


def test_store_keeps_pending_state_when_file_remains_locked(tmp_path, monkeypatch) -> None:
    """Kiểm tra lỗi khóa kéo dài không làm chết UI và bản mới vẫn sống trong RAM."""
    store = JsonStore(tmp_path / "state.json")

    def always_locked(_source, _destination) -> None:
        """Giả lập file đích bị OneDrive giữ suốt toàn bộ số lần retry."""
        raise PermissionError("persistent OneDrive lock")

    monkeypatch.setattr("aris.storage.json_store.os.replace", always_locked)
    monkeypatch.setattr("aris.storage.json_store.time.sleep", lambda _seconds: None)

    state = store.update(selected_model="iron_man_mask")

    assert state["selected_model"] == "iron_man_mask"
    assert store.persistence_pending
    assert store.load()["selected_model"] == "iron_man_mask"
