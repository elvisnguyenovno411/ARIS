from __future__ import annotations

import time
from pathlib import Path

from aris.ai.router import IntentRouter
from aris.desktop.actions import DesktopActions
from aris.desktop.safe_paths import SafePathPolicy
from aris.models.catalog import ModelCatalog


def main() -> int:
    """Mở Notepad rỗng rồi đóng bằng WM_CLOSE để kiểm tra trọn đường lệnh an toàn."""
    actions = DesktopActions(SafePathPolicy([Path.cwd()]))
    router = IntentRouter(ModelCatalog())
    open_intent = router.route("Mở Notepad")
    close_intent = router.route("Đóng Notepad")
    opened = actions.open_app(str(open_intent.arguments["app"]))
    if not opened.success:
        print("WINDOW_ACTION_PROBE failed stage=open")
        return 1

    closed = None
    for _ in range(20):
        time.sleep(0.25)
        closed = actions.close_app(str(close_intent.arguments["app"]))
        if closed.success:
            break

    if closed is None or not closed.success:
        print("WINDOW_ACTION_PROBE failed stage=close")
        return 2
    print(
        "WINDOW_ACTION_PROBE ok "
        f"open_intent={open_intent.kind.value} close_intent={close_intent.kind.value} "
        f"windows={closed.data.get('window_count', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
