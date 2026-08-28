from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def choose_input_device(
    devices: Sequence[Mapping[str, Any]],
    default_index: int | None,
    requested: str | None = None,
) -> int | None:
    """Chọn mic theo override, ưu tiên mic array laptop rồi mới dùng mặc định Windows."""
    input_devices = [
        (index, device)
        for index, device in enumerate(devices)
        if int(device.get("max_input_channels", 0)) > 0
    ]
    if not input_devices:
        return None

    normalized_request = (requested or "").strip().casefold()
    if normalized_request:
        if normalized_request.isdigit():
            requested_index = int(normalized_request)
            if any(index == requested_index for index, _ in input_devices):
                return requested_index
        for index, device in input_devices:
            if normalized_request in str(device.get("name", "")).casefold():
                return index

    # Mic array là microphone tích hợp laptop; cổng "Microphone" thường là jack rời đang trống.
    for index, device in input_devices:
        if "microphone array" in str(device.get("name", "")).casefold():
            return index

    if default_index is not None and any(index == default_index for index, _ in input_devices):
        return default_index
    return input_devices[0][0]
