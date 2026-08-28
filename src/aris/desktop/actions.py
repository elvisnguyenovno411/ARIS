from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import webbrowser
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

from aris.core.types import ActionResult
from aris.desktop.safe_paths import SafePathPolicy

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WM_CLOSE = 0x0010


@dataclass(frozen=True, slots=True)
class LaunchSpec:
    """Mô tả cách mở một ứng dụng allowlist mà không dùng shell tùy ý."""

    key: str
    display_name: str
    candidates: tuple[Path, ...] = ()
    command: tuple[str, ...] = ()
    process_names: tuple[str, ...] = ()


def localize_open_app_result(result: ActionResult, language: str) -> ActionResult:
    """Đổi phản hồi mở app sang tiếng Việt khi cần nhưng giữ nguyên trạng thái và dữ liệu."""
    if language != "vi":
        return result
    display_name = str(result.data.get("display_name", "ứng dụng"))
    if result.success:
        message = f"Đang mở {display_name}."
    elif "not found" in result.message.casefold():
        message = f"Không tìm thấy {display_name} trên máy này."
    else:
        message = f"Không thể mở {display_name}."
    return ActionResult(result.success, message, result.data)


def localize_close_app_result(result: ActionResult, language: str) -> ActionResult:
    """Đổi phản hồi đóng app sang tiếng Việt nhưng giữ nguyên metadata kiểm thử."""
    if language != "vi":
        return result
    display_name = str(result.data.get("display_name", "ứng dụng"))
    if result.success:
        message = f"Đã gửi yêu cầu đóng {display_name}."
    elif "not running" in result.message.casefold():
        message = f"{display_name} hiện không có cửa sổ đang mở."
    elif "not supported" in result.message.casefold():
        message = f"ARIS chưa hỗ trợ đóng an toàn {display_name}."
    else:
        message = f"Không thể đóng {display_name}."
    return ActionResult(result.success, message, result.data)


def _program_files_x86() -> Path:
    """Trả về Program Files (x86) hoặc thư mục thay thế an toàn trên Windows."""
    return Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))


def default_launch_specs() -> dict[str, LaunchSpec]:
    """Tạo allowlist ứng dụng với các vị trí cài đặt phổ biến trên Windows 11."""
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    code_from_path = shutil.which("code")
    paint_from_path = shutil.which("mspaint")
    terminal_from_path = shutil.which("wt")
    specs = (
        LaunchSpec(
            "chrome",
            "Google Chrome",
            (
                program_files / "Google" / "Chrome" / "Application" / "chrome.exe",
                _program_files_x86() / "Google" / "Chrome" / "Application" / "chrome.exe",
                local / "Google" / "Chrome" / "Application" / "chrome.exe",
            ),
            process_names=("chrome.exe",),
        ),
        LaunchSpec(
            "vscode",
            "Visual Studio Code",
            tuple(
                path
                for path in (
                    local / "Programs" / "Microsoft VS Code" / "Code.exe",
                    Path(code_from_path) if code_from_path else None,
                )
                if path is not None
            ),
            process_names=("code.exe",),
        ),
        LaunchSpec(
            "discord",
            "Discord",
            (local / "Discord" / "Update.exe",),
            ("--processStart", "Discord.exe"),
            ("discord.exe",),
        ),
        LaunchSpec(
            "codex",
            "Codex",
            command=(
                "explorer.exe",
                r"shell:AppsFolder\OpenAI.Codex_2p2nqsd0c76g0!App",
            ),
            process_names=("codex.exe",),
        ),
        LaunchSpec(
            "edge",
            "Microsoft Edge",
            (
                program_files / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                _program_files_x86()
                / "Microsoft"
                / "Edge"
                / "Application"
                / "msedge.exe",
            ),
            process_names=("msedge.exe",),
        ),
        LaunchSpec("file_explorer", "File Explorer", command=("explorer.exe",)),
        LaunchSpec(
            "notepad",
            "Notepad",
            (windows / "System32" / "notepad.exe",),
            process_names=("notepad.exe",),
        ),
        LaunchSpec(
            "calculator",
            "Calculator",
            (windows / "System32" / "calc.exe",),
        ),
        LaunchSpec(
            "paint",
            "Microsoft Paint",
            tuple(
                path
                for path in (
                    Path(paint_from_path) if paint_from_path else None,
                    local / "Microsoft" / "WindowsApps" / "mspaint.exe",
                )
                if path is not None
            ),
            process_names=("mspaint.exe",),
        ),
        LaunchSpec(
            "terminal",
            "Windows Terminal",
            tuple(
                path
                for path in (
                    Path(terminal_from_path) if terminal_from_path else None,
                    local / "Microsoft" / "WindowsApps" / "wt.exe",
                )
                if path is not None
            ),
            process_names=("windowsterminal.exe",),
        ),
        LaunchSpec(
            "settings",
            "Windows Settings",
            command=("explorer.exe", "ms-settings:"),
        ),
        LaunchSpec(
            "spotify",
            "Spotify",
            command=(
                "explorer.exe",
                r"shell:AppsFolder\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify",
            ),
            process_names=("spotify.exe",),
        ),
        LaunchSpec(
            "snipping_tool",
            "Snipping Tool",
            command=(
                "explorer.exe",
                r"shell:AppsFolder\Microsoft.ScreenSketch_8wekyb3d8bbwe!App",
            ),
            process_names=("snippingtool.exe",),
        ),
    )
    return {spec.key: spec for spec in specs}


class DesktopActions:
    """Thực thi tập hành động Windows nhỏ, rõ ràng và có allowlist."""

    def __init__(self, path_policy: SafePathPolicy) -> None:
        """Khởi tạo dịch vụ với chính sách đường dẫn và danh sách ứng dụng cố định."""
        self.path_policy = path_policy
        self.launch_specs = default_launch_specs()

    def open_app(self, key: str) -> ActionResult:
        """Mở ứng dụng allowlist bằng argv cố định và không dùng `shell=True`."""
        spec = self.launch_specs.get(key)
        if spec is None:
            return ActionResult(False, "That application is not in the ARIS allowlist.")
        result_data = {"app": spec.key, "display_name": spec.display_name}
        try:
            if spec.candidates:
                executable = next((path for path in spec.candidates if path.exists()), None)
                if executable is None:
                    return ActionResult(
                        False,
                        f"{spec.display_name} was not found on this PC.",
                        result_data,
                    )
                subprocess.Popen(
                    [str(executable), *spec.command],
                    close_fds=True,
                    creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                )
            else:
                subprocess.Popen(
                    list(spec.command),
                    close_fds=True,
                    creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                )
        except OSError as error:
            return ActionResult(
                False,
                f"Could not open {spec.display_name}: {error}",
                result_data,
            )
        return ActionResult(True, f"Opening {spec.display_name}.", result_data)

    def close_app(self, key: str) -> ActionResult:
        """Gửi WM_CLOSE tới cửa sổ app allowlist để app có cơ hội hỏi lưu dữ liệu."""
        spec = self.launch_specs.get(key)
        if spec is None:
            return ActionResult(False, "That application is not in the ARIS allowlist.")
        result_data = {"app": spec.key, "display_name": spec.display_name}
        if not spec.process_names:
            return ActionResult(
                False,
                f"Safe window closing is not supported for {spec.display_name}.",
                result_data,
            )
        if os.name != "nt":
            return ActionResult(False, "Window closing is available only on Windows.", result_data)
        handles = self._matching_visible_windows(spec.process_names)
        if not handles:
            return ActionResult(
                False,
                f"{spec.display_name} is not running.",
                result_data,
            )
        closed = sum(1 for handle in handles if self._request_window_close(handle))
        result_data["window_count"] = closed
        if closed == 0:
            return ActionResult(False, f"Could not close {spec.display_name}.", result_data)
        return ActionResult(True, f"Closing {spec.display_name}.", result_data)

    @staticmethod
    def _matching_visible_windows(process_names: tuple[str, ...]) -> list[int]:
        """Liệt kê cửa sổ hiển thị thuộc đúng executable allowlist bằng Win32 API."""
        allowed = {name.casefold() for name in process_names}
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        handles: list[int] = []

        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit_window(hwnd: int, _lparam: int) -> bool:
            """Thu thập handle nếu cửa sổ hiển thị thuộc đúng tiến trình được phép."""
            if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) <= 0:
                return True
            process_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            process = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                process_id.value,
            )
            if not process:
                return True
            try:
                executable = ctypes.create_unicode_buffer(32_768)
                size = wintypes.DWORD(len(executable))
                if kernel32.QueryFullProcessImageNameW(
                    process,
                    0,
                    executable,
                    ctypes.byref(size),
                ) and Path(executable.value).name.casefold() in allowed:
                    handles.append(int(hwnd))
            finally:
                kernel32.CloseHandle(process)
            return True

        user32.EnumWindows(callback_type(visit_window), 0)
        return handles

    @staticmethod
    def _request_window_close(handle: int) -> bool:
        """Gửi thông điệp đóng không cưỡng bức đến đúng handle đã được kiểm tra."""
        return bool(ctypes.windll.user32.PostMessageW(handle, WM_CLOSE, 0, 0))

    def google_search(self, query: str) -> ActionResult:
        """Mở truy vấn đã mã hóa trong trình duyệt mặc định mà không chạy mã web."""
        cleaned = query.strip()
        if not cleaned:
            return ActionResult(False, "Please provide a Google search query.")
        url = f"https://www.google.com/search?q={quote_plus(cleaned)}"
        opened = webbrowser.open(url, new=2)
        return ActionResult(opened, f"Searching Google for: {cleaned}", {"url": url})

    def find_files(self, query: str) -> ActionResult:
        """Tìm file trong các thư mục cho phép và trả về tối đa tám kết quả."""
        matches = self.path_policy.find(query)
        if not matches:
            return ActionResult(False, f"No safe file matched '{query}'.")
        return ActionResult(
            True,
            f"Found {len(matches)} safe match{'es' if len(matches) != 1 else ''}.",
            {"matches": [str(path) for path in matches]},
        )

    def open_file(self, path: Path) -> ActionResult:
        """Mở một file/thư mục đã qua kiểm tra allowlist bằng ứng dụng mặc định."""
        try:
            safe_path = self.path_policy.require_allowed(path)
            os.startfile(safe_path)  # type: ignore[attr-defined]
        except (OSError, ValueError) as error:
            return ActionResult(False, f"Could not open the requested file: {error}")
        return ActionResult(True, f"Opening {safe_path.name}.", {"path": str(safe_path)})

    def change_volume(
        self, operation: str, steps: int = 3, percent: int | None = None
    ) -> ActionResult:
        """Điều chỉnh âm lượng Windows theo bước, mức đích hoặc phần trăm tương đối."""
        if os.name != "nt":
            return ActionResult(False, "Volume control is available only on Windows.")
        if operation == "mute":
            self._press_media_key(VK_VOLUME_MUTE, 1)
            return ActionResult(True, "Toggling mute.")
        if operation == "set" and percent is not None:
            target = max(0, min(100, int(percent)))
            self._press_media_key(VK_VOLUME_DOWN, 50)
            self._press_media_key(VK_VOLUME_UP, round(target / 2))
            return ActionResult(True, f"Volume set to approximately {target}%.")
        if operation in {"down", "up"} and percent is not None:
            amount = max(0, min(100, int(percent)))
            if amount == 0:
                return ActionResult(True, "Volume unchanged.")
            repeats = max(1, round(amount / 2))
            key = VK_VOLUME_DOWN if operation == "down" else VK_VOLUME_UP
            self._press_media_key(key, repeats)
            direction = "Lowering" if operation == "down" else "Raising"
            return ActionResult(True, f"{direction} volume by approximately {amount}%.")
        safe_steps = max(1, min(20, int(steps)))
        key = VK_VOLUME_DOWN if operation == "down" else VK_VOLUME_UP
        self._press_media_key(key, safe_steps)
        direction = "down" if operation == "down" else "up"
        return ActionResult(True, f"Turning volume {direction}.")

    @staticmethod
    def _press_media_key(key_code: int, repeats: int) -> None:
        """Gửi một phím media cố định qua Win32; không nhận mã phím từ người dùng."""
        user32 = ctypes.windll.user32
        for _ in range(max(1, min(50, repeats))):
            user32.keybd_event(key_code, 0, 0, 0)
            user32.keybd_event(key_code, 0, KEYEVENTF_KEYUP, 0)
