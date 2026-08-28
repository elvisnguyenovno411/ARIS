from aris.models.catalog import ModelCatalog


def test_catalog_contains_six_models() -> None:
    """Kiểm tra beta luôn công bố đúng sáu model đã chốt."""
    catalog = ModelCatalog()
    assert len(catalog.all()) == 6


def test_catalog_matches_vietnamese_and_english() -> None:
    """Kiểm tra tên model được nhận diện bằng cả tiếng Việt lẫn tiếng Anh."""
    catalog = ModelCatalog()
    assert catalog.match("Show me the Iron Man Mask").key == "iron_man_mask"
    assert catalog.match("cho mình xem máy bắn tơ").key == "web_shooter"
