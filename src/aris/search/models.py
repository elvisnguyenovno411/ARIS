from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchSource:
    """Chứa tiêu đề và URL http/https đã kiểm tra của một nguồn tra cứu."""

    title: str
    url: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Biểu diễn câu trả lời web có nguồn an toàn để worker chuyển sang HUD."""

    success: bool
    query: str
    answer: str
    sources: tuple[SearchSource, ...] = ()
    error_code: str | None = None
    cached: bool = False
    request_number: int = 0
