from __future__ import annotations

from aris.core.config import AppConfig
from aris.search import ArisWebSearch


def main() -> int:
    """Gọi đúng một tra cứu công khai và chỉ in metadata, tuyệt đối không in API key."""
    search = ArisWebSearch(AppConfig.load())
    if not search.api_enabled:
        print("WEB_SEARCH_PROBE enabled=false")
        return 2
    result = search.search("What is the official OpenAI API web search documentation?")
    print(
        "WEB_SEARCH_PROBE "
        f"success={str(result.success).lower()} "
        f"sources={len(result.sources)} "
        f"remaining={search.requests_remaining} "
        f"error={result.error_code or 'none'}"
    )
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
