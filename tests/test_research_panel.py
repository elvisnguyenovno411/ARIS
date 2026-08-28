from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget

from aris.search.models import SearchResult, SearchSource
from aris.ui.research_manager import ResearchPanelManager, research_panel_position
from aris.ui.research_panel import ResearchPanel
from aris.vision.spatial_gesture import SpatialGestureFrame, SpatialGestureMode


def test_research_panel_shows_plain_answer_sources_and_remaining_budget(qtbot) -> None:
    """Kiểm tra bảng hologram hiện dữ liệu/nguồn và không diễn giải text như HTML."""
    panel = ResearchPanel("research-test")
    qtbot.addWidget(panel)
    result = SearchResult(
        True,
        "robot mới nhất",
        "<b>Nội dung phải là text thuần.</b>",
        (SearchSource("Nguồn chính", "https://example.com/source"),),
        request_number=1,
    )

    panel.show_result(result, requests_remaining=19)
    panel.answer_label.show_text(result.answer, animated=False)

    assert panel.state_label.text() == "GROUNDED RESPONSE · ONLINE"
    assert panel.answer_label.text() == "<b>Nội dung phải là text thuần.</b>"
    assert panel.answer_label.textFormat().name == "PlainText"
    assert panel._source_buttons[0].property("sourceUrl") == "https://example.com/source"
    assert "19 REQUESTS LEFT" in panel.meta_label.text()


def test_research_panel_loading_and_close_are_local(qtbot) -> None:
    """Kiểm tra loading không mở trình duyệt và nút đóng chỉ phát signal nội bộ."""
    panel = ResearchPanel("research-test")
    qtbot.addWidget(panel)
    closed: list[bool] = []
    closed: list[str] = []
    panel.close_requested.connect(closed.append)

    panel.show_loading("kính AR")
    panel.close_button.click()

    assert panel.query_label.text() == "kính AR"
    assert closed == ["research-test"]


def test_manager_keeps_multiple_research_panels_and_selects_latest(qtbot) -> None:
    """Kiểm tra ba bảng cùng tồn tại, có ID riêng và bảng mới nhất nằm trên cùng."""
    container = QWidget()
    container.resize(1500, 850)
    qtbot.addWidget(container)
    container.show()
    manager = ResearchPanelManager(container)

    panel_ids = [manager.open_loading(f"query {index}") for index in range(3)]

    assert manager.panel_ids == tuple(panel_ids)
    assert manager.active_id == panel_ids[-1]
    positions = [manager.panel(panel_id).pos() for panel_id in panel_ids]
    assert len({(position.x(), position.y()) for position in positions}) == 3


def test_manager_closes_only_selected_panel_then_can_close_all(qtbot) -> None:
    """Kiểm tra close mặc định chỉ xóa bảng chọn còn close-all dọn toàn bộ timer/widget."""
    container = QWidget()
    container.resize(1500, 850)
    qtbot.addWidget(container)
    manager = ResearchPanelManager(container)
    first = manager.open_loading("first")
    second = manager.open_loading("second")
    manager.select_panel(first)

    assert manager.close_panel() is True
    qtbot.wait(280)
    assert manager.panel_ids == (second,)

    manager.close_all(animated=False)
    assert manager.has_panels is False


def test_research_panel_positions_are_clamped_and_alternate_sides() -> None:
    """Kiểm tra vị trí mặc định nằm trong HUD và xen kẽ hai bên thay vì chồng hoàn toàn."""
    container_size = QSize(1600, 900)
    panel_size = QSize(420, 460)

    positions = [research_panel_position(container_size, panel_size, index) for index in range(4)]

    assert positions[0].x() > positions[1].x()
    assert len(set(positions)) == 4
    for position in positions:
        assert position.x() >= 0
        assert position.y() >= 0
        assert position.x() + panel_size.width() <= container_size.width()
        assert position.y() + panel_size.height() <= container_size.height()


def test_open_hand_moves_only_the_selected_research_panel(qtbot) -> None:
    """Kiểm tra MOVE theo tay dùng smoothing và không kéo bảng không được chọn."""
    container = QWidget()
    container.resize(1500, 850)
    qtbot.addWidget(container)
    manager = ResearchPanelManager(container)
    first = manager.open_loading("first")
    second = manager.open_loading("second")
    manager.select_panel(first)
    first_panel = manager.panel(first)
    second_panel = manager.panel(second)
    qtbot.wait(320)
    first_before = first_panel.pos()
    second_before = second_panel.pos()

    manager.apply_spatial_gesture(
        SpatialGestureFrame(mode=SpatialGestureMode.MOVE, move_x=0.03, move_y=0.02)
    )
    qtbot.wait(180)

    assert first_panel.pos() != first_before
    assert second_panel.pos() == second_before


def test_pinch_transform_does_not_move_research_panel(qtbot) -> None:
    """Đảm bảo pinch dành cho model không vô tình xoay hoặc di chuyển bảng thông tin."""
    container = QWidget()
    container.resize(1500, 850)
    qtbot.addWidget(container)
    manager = ResearchPanelManager(container)
    panel_id = manager.open_loading("first")
    qtbot.wait(320)
    panel = manager.panel(panel_id)
    before = panel.pos()

    manager.apply_spatial_gesture(
        SpatialGestureFrame(mode=SpatialGestureMode.TRANSFORM, yaw=8.0)
    )
    qtbot.wait(80)

    assert panel.pos() == before


def test_vertical_pinch_scrolls_only_selected_research_content(qtbot) -> None:
    """Kiểm tra kéo pinch lên cuộn xuống nội dung mà không đổi vị trí cả bảng."""
    container = QWidget()
    container.resize(1500, 850)
    qtbot.addWidget(container)
    container.show()
    manager = ResearchPanelManager(container)
    panel_id = manager.open_loading("long research")
    panel = manager.panel(panel_id)
    panel.show_result(
        SearchResult(
            True,
            "long research",
            "Nội dung kiểm thử. " * 240,
            cached=True,
        ),
        requests_remaining=19,
    )
    scrollbar = panel.scroll_area.verticalScrollBar()
    qtbot.waitUntil(lambda: scrollbar.maximum() > 0, timeout=1200)
    qtbot.wait(320)
    before_position = panel.pos()
    manager.apply_spatial_gesture(
        SpatialGestureFrame(mode=SpatialGestureMode.TRANSFORM, move_y=-0.05)
    )
    qtbot.wait(180)

    assert scrollbar.value() > 0
    assert panel.pos() == before_position
