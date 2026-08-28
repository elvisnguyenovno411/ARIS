from pathlib import Path

from aris.core.types import ActionResult
from aris.desktop.actions import (
    DesktopActions,
    default_launch_specs,
    localize_close_app_result,
    localize_open_app_result,
)
from aris.desktop.safe_paths import SafePathPolicy


def test_unknown_app_is_rejected(tmp_path: Path) -> None:
    """Kiểm tra ứng dụng ngoài allowlist bị từ chối trước khi tạo tiến trình."""
    actions = DesktopActions(SafePathPolicy([tmp_path]))
    result = actions.open_app("powershell")
    assert not result.success
    assert "allowlist" in result.message


def test_extended_launch_specs_use_only_fixed_safe_targets() -> None:
    """Kiểm tra app mở rộng có khóa cố định và Terminal không nhận lệnh từ người dùng."""
    specs = default_launch_specs()

    assert {
        "edge",
        "file_explorer",
        "notepad",
        "calculator",
        "paint",
        "terminal",
        "settings",
        "spotify",
        "snipping_tool",
    }.issubset(specs)
    assert specs["terminal"].command == ()
    assert all(path.name.casefold() == "wt.exe" for path in specs["terminal"].candidates)
    assert specs["settings"].command == ("explorer.exe", "ms-settings:")


def test_command_launch_never_enables_shell(tmp_path: Path, monkeypatch) -> None:
    """Kiểm tra Settings chỉ truyền argv cố định trực tiếp vào Popen và không bật shell."""
    calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(
        "aris.desktop.actions.subprocess.Popen",
        lambda argv, **kwargs: calls.append((argv, kwargs)),
    )
    actions = DesktopActions(SafePathPolicy([tmp_path]))

    result = actions.open_app("settings")

    assert result.success
    assert calls[0][0] == ["explorer.exe", "ms-settings:"]
    assert "shell" not in calls[0][1]


def test_open_app_response_is_localized_without_losing_metadata() -> None:
    """Kiểm tra HUD tiếng Việt đọc tên app và vẫn giữ metadata allowlist ban đầu."""
    original = ActionResult(
        True,
        "Opening Calculator.",
        {"app": "calculator", "display_name": "Calculator"},
    )

    localized = localize_open_app_result(original, "vi")

    assert localized.message == "Đang mở Calculator."
    assert localized.data == original.data


def test_close_app_sends_graceful_message_only_to_allowlisted_windows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Kiểm tra đóng app dùng handle đã lọc và không gọi taskkill cưỡng bức."""
    actions = DesktopActions(SafePathPolicy([tmp_path]))
    requested: list[int] = []
    monkeypatch.setattr(actions, "_matching_visible_windows", lambda _names: [101, 202])
    monkeypatch.setattr(
        actions,
        "_request_window_close",
        lambda handle: requested.append(handle) or True,
    )

    result = actions.close_app("chrome")

    assert result.success
    assert result.data["window_count"] == 2
    assert requested == [101, 202]


def test_close_app_rejects_unsupported_or_unknown_target(tmp_path: Path) -> None:
    """Kiểm tra ARIS không đóng Explorer hoặc executable ngoài allowlist an toàn."""
    actions = DesktopActions(SafePathPolicy([tmp_path]))

    assert not actions.close_app("file_explorer").success
    assert not actions.close_app("powershell").success


def test_close_app_response_is_localized_without_losing_metadata() -> None:
    """Kiểm tra phản hồi đóng app tiếng Việt vẫn bảo toàn số cửa sổ đã yêu cầu đóng."""
    original = ActionResult(
        True,
        "Closing Google Chrome.",
        {"app": "chrome", "display_name": "Google Chrome", "window_count": 2},
    )

    localized = localize_close_app_result(original, "vi")

    assert localized.message == "Đã gửi yêu cầu đóng Google Chrome."
    assert localized.data == original.data


def test_file_search_returns_only_safe_matches(tmp_path: Path) -> None:
    """Kiểm tra tìm file chỉ trả kết quả nằm trong thư mục cho phép."""
    wanted = tmp_path / "portfolio_notes.txt"
    wanted.write_text("ARIS", encoding="utf-8")
    actions = DesktopActions(SafePathPolicy([tmp_path]))
    result = actions.find_files("portfolio")
    assert result.success
    assert result.data["matches"] == [str(wanted)]


def test_relative_volume_percentage_uses_two_percent_media_key_steps(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Kiểm tra giảm 30% tạo 15 lần nhấn media thay vì mức trần sai 20 lần."""
    actions = DesktopActions(SafePathPolicy([tmp_path]))
    calls: list[tuple[int, int]] = []
    monkeypatch.setattr(
        actions,
        "_press_media_key",
        lambda key, repeats: calls.append((key, repeats)),
    )

    result = actions.change_volume("down", percent=30)

    assert result.success
    assert calls[0][1] == 15
    assert "30%" in result.message
