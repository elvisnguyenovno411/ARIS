from aris.media.music_query import normalize_music_query


def test_minh_anh_noi_nay_is_not_confused_with_son_tung_song() -> None:
    """Kiểm tra các biến thể STT thiếu `có` đều giữ đúng bài của NIT và SING."""
    variants = (
        "mình anh ơi này remix",
        "mình đang nơi này remix",
        "bật nhạc mình anh nơi này remix",
    )

    for query in variants:
        assert normalize_music_query(query) == "Mình Anh Nơi Này Remix NIT ft Sing"


def test_noi_nay_co_anh_requires_the_word_co() -> None:
    """Kiểm tra chỉ tên có từ `có` mới được ánh xạ sang bài của Sơn Tùng M-TP."""
    assert (
        normalize_music_query("mở nhạc Nơi này có anh")
        == "Nơi này có anh Sơn Tùng M-TP official audio"
    )


def test_minh_anh_noi_nay_preserves_explicit_remix_request() -> None:
    """Kiểm tra người dùng nói remix thì ARIS không tự đổi về bản gốc."""
    assert (
        normalize_music_query("mở Mình Anh Nơi Này Remix")
        == "Mình Anh Nơi Này Remix NIT ft Sing"
    )


def test_music_command_prefix_is_removed_before_youtube_search() -> None:
    """Kiểm tra target AI lỡ giữ cả động từ vẫn chỉ gửi tên bài sang YouTube."""
    assert normalize_music_query("bật nhạc Blinding Lights") == "blinding lights"
