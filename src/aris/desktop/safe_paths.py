from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

SKIP_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "$recycle.bin",
}

BLOCKED_PERSONAL_MEDIA_EXTENSIONS = frozenset(
    {
        ".aac",
        ".avi",
        ".flac",
        ".m4a",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp3",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".ogg",
        ".wav",
        ".webm",
        ".wma",
    }
)


class UnsafePathError(ValueError):
    """Báo lỗi khi đường dẫn nằm ngoài các thư mục chỉ-đọc đã cho phép."""


class SafePathPolicy:
    """Xác thực và tìm file chỉ bên trong các thư mục người dùng đã cho phép."""

    def __init__(self, roots: Iterable[Path]) -> None:
        """Chuẩn hóa danh sách thư mục gốc và loại bỏ mục bị trùng."""
        normalized: dict[str, Path] = {}
        for root in roots:
            resolved = root.resolve(strict=False)
            normalized[os.path.normcase(str(resolved))] = resolved
        self.roots = tuple(normalized.values())

    def is_allowed(self, path: Path) -> bool:
        """Kiểm tra đường dẫn có nằm trong ít nhất một thư mục cho phép hay không."""
        candidate = path.expanduser().resolve(strict=False)
        if candidate.suffix.casefold() in BLOCKED_PERSONAL_MEDIA_EXTENSIONS:
            return False
        return any(candidate == root or root in candidate.parents for root in self.roots)

    def require_allowed(self, path: Path, must_exist: bool = True) -> Path:
        """Trả về đường dẫn an toàn hoặc phát sinh lỗi nếu nằm ngoài phạm vi."""
        candidate = path.expanduser().resolve(strict=False)
        if not self.is_allowed(candidate):
            raise UnsafePathError("The requested path is outside ARIS safe folders.")
        if must_exist and not candidate.exists():
            raise FileNotFoundError(candidate)
        return candidate

    def find(self, query: str, limit: int = 8) -> list[Path]:
        """Tìm tối đa `limit` file/thư mục theo tên mà không quét ngoài allowlist."""
        cleaned = query.strip().strip("\"'").casefold()
        if not cleaned:
            return []
        explicit = Path(query.strip().strip("\"'"))
        if explicit.is_absolute():
            try:
                return [self.require_allowed(explicit)]
            except (UnsafePathError, FileNotFoundError):
                return []

        matches: list[Path] = []
        for root in self.roots:
            if not root.exists():
                continue
            for current, directories, files in os.walk(root):
                directories[:] = [
                    name
                    for name in directories
                    if name.casefold() not in SKIP_DIRECTORIES and not name.startswith(".")
                ]
                names = directories + files
                for name in names:
                    if cleaned in name.casefold():
                        candidate = Path(current) / name
                        if self.is_allowed(candidate):
                            matches.append(candidate)
                            if len(matches) >= limit:
                                return matches
        return matches
