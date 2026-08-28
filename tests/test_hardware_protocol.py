from aris.hardware.protocol import (
    GuardState,
    HardwareEventType,
    normalize_hardware_command,
    parse_hardware_line,
)


def test_parses_guard_state_and_distance_events() -> None:
    """Kiểm tra protocol nhận đúng state và số đo nhưng không cần mở cổng COM thật."""
    state = parse_hardware_line("ARIS_HW|STATE|ALERT")
    distance = parse_hardware_line("ARIS_HW|DISTANCE_CM|42.5")

    assert state is not None
    assert state.kind is HardwareEventType.STATE
    assert GuardState(state.value) is GuardState.ALERT
    assert distance is not None
    assert distance.value == "42.5"


def test_rejects_malformed_or_untrusted_hardware_lines() -> None:
    """Đảm bảo dữ liệu Serial lạ không được biến thành trạng thái hay hành động ARIS."""
    invalid_lines = (
        "STATE|ALERT",
        "ARIS_HW|STATE|UNKNOWN",
        "ARIS_HW|DISTANCE_CM|not-a-number",
        "ARIS_HW|DISTANCE_CM|50000",
        "ARIS_HW|SHELL|format c:",
    )

    assert all(parse_hardware_line(line) is None for line in invalid_lines)


def test_serial_commands_use_a_fixed_allowlist() -> None:
    """Đảm bảo Python chỉ có thể gửi bốn lệnh guard đã được duyệt sang Arduino."""
    assert normalize_hardware_command(" arm ") == "ARM"
    assert normalize_hardware_command("status") == "STATUS"
    assert normalize_hardware_command("OPEN CHROME") is None
    assert normalize_hardware_command("DISARM; DELETE") is None
