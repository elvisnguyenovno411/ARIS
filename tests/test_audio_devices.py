from aris.voice.devices import choose_input_device

DEVICES = [
    {"name": "Microphone", "max_input_channels": 2},
    {"name": "Microphone Array (Realtek)", "max_input_channels": 2},
    {"name": "Speakers", "max_input_channels": 0},
]


def test_laptop_microphone_array_is_preferred_over_empty_jack() -> None:
    """Kiểm tra mic array được chọn thay vì cổng microphone rời mặc định."""
    assert choose_input_device(DEVICES, default_index=0) == 1


def test_explicit_device_name_overrides_array_preference() -> None:
    """Kiểm tra người dùng vẫn có thể chọn mic khác bằng tên trong `.env`."""
    assert choose_input_device(DEVICES, default_index=0, requested="Microphone") == 0


def test_invalid_override_falls_back_to_array() -> None:
    """Kiểm tra override sai không làm mất microphone tích hợp an toàn."""
    assert choose_input_device(DEVICES, default_index=0, requested="missing") == 1
