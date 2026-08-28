from aris.ai.router import IntentRouter
from aris.core.types import IntentType
from aris.models.catalog import ModelCatalog


def make_router() -> IntentRouter:
    """Tạo router dùng chung cho các ca kiểm thử định tuyến."""
    return IntentRouter(ModelCatalog())


def test_routes_allowlisted_app() -> None:
    """Kiểm tra lệnh mở ứng dụng chỉ trả về khóa allowlist."""
    intent = make_router().route("Mở VS Code")
    assert intent.kind is IntentType.OPEN_APP
    assert intent.arguments["app"] == "vscode"


def test_routes_close_app_before_generic_model_close() -> None:
    """Kiểm tra đóng app song ngữ không bị hiểu nhầm thành đóng model hologram."""
    commands = {
        "Đóng Chrome": "chrome",
        "Tắt VS Code": "vscode",
        "Close Discord": "discord",
        "Quit Codex": "codex",
    }

    for command, app_key in commands.items():
        intent = make_router().route(command)
        assert intent.kind is IntentType.CLOSE_APP
        assert intent.arguments == {"app": app_key}


def test_routes_natural_close_app_word_order_and_synonyms() -> None:
    """Kiểm tra câu đóng app linh hoạt vẫn giữ đúng target allowlist."""
    commands = {
        "Bạn có thể giúp mình kết thúc Discord được không?": "discord",
        "Please shut Chrome down": "chrome",
        "Terminate VS Code now": "vscode",
        "Cho Codex ngừng lại": "codex",
    }

    for command, app_key in commands.items():
        intent = make_router().route(command)
        assert intent.kind is IntentType.CLOSE_APP
        assert intent.arguments == {"app": app_key}


def test_routes_local_music_commands_without_cloud() -> None:
    """Kiểm tra phát/tạm dừng/tiếp tục nhạc dùng ba intent local riêng biệt."""
    play = make_router().route("Phát nhạc bài Midnight City")
    youtube_style = make_router().route("Bật nhạc Nơi này có anh")
    pause = make_router().route("Tạm dừng")
    resume = make_router().route("Tiếp tục")
    stop = make_router().route("Tắt nhạc")

    assert play.kind is IntentType.PLAY_MUSIC
    assert play.arguments == {"query": "midnight city"}
    assert youtube_style.kind is IntentType.PLAY_MUSIC
    assert youtube_style.arguments == {"query": "noi nay co anh"}
    assert pause.kind is IntentType.PAUSE_MUSIC
    assert resume.kind is IntentType.RESUME_MUSIC
    assert stop.kind is IntentType.STOP_MUSIC


def test_stop_music_vocabulary_never_routes_to_shutdown_or_pause() -> None:
    """Kiểm tra dừng/ngừng nhạc xóa playback thay vì tắt ARIS hoặc chỉ pause."""
    for command in (
        "Dừng nhạc",
        "Ngừng nhạc",
        "Dừng bài hát",
        "Ngừng bài hát",
        "Dừng phát nhạc",
    ):
        assert make_router().route(command, music_context=True).kind is IntentType.STOP_MUSIC

    assert make_router().route("Tạm dừng nhạc").kind is IntentType.PAUSE_MUSIC


def test_contextual_pronoun_stops_only_when_music_is_selected() -> None:
    """Kiểm tra `tắt nó/stop it` tắt bài hiện tại nhưng không đoán bừa khi thiếu ngữ cảnh."""
    router = make_router()

    assert router.route("Tắt nó", music_context=True).kind is IntentType.STOP_MUSIC
    assert router.route("Stop it", music_context=True).kind is IntentType.STOP_MUSIC
    assert router.route("Tắt nó", music_context=False).kind is IntentType.GENERAL_CHAT


def test_new_music_request_replaces_track_name_in_intent() -> None:
    """Kiểm tra mỗi lệnh phát bài mới mang đúng tên để player hủy vòng lặp cũ."""
    first = make_router().route("Play music Believer")
    second = make_router().route("Phát bài Blinding Lights")

    assert first.arguments == {"query": "believer"}
    assert second.arguments == {"query": "blinding lights"}


def test_known_song_without_music_noun_stays_on_fast_local_router() -> None:
    """Kiểm tra `mở Mình Anh Nơi Này Remix` không phải chờ AI đoán intent."""
    intent = make_router().route("Mở Mình Anh Nơi Này Remix")

    assert intent.kind is IntentType.PLAY_MUSIC
    assert intent.arguments == {"query": "minh anh noi nay remix"}


def test_routes_music_volume_separately_from_windows_volume() -> None:
    """Kiểm tra âm lượng nhạc có intent riêng và giữ đúng mức tăng/giảm/đích."""
    commands = {
        "âm lượng nhạc 50%": {"operation": "set", "percent": 50},
        "tăng âm lượng nhạc 10%": {"operation": "up", "percent": 10},
        "giảm âm lượng nhạc 20%": {"operation": "down", "percent": 20},
    }

    for command, arguments in commands.items():
        intent = make_router().route(command)
        assert intent.kind is IntentType.MUSIC_VOLUME
        assert intent.arguments == arguments


def test_routes_extended_windows_app_allowlist() -> None:
    """Kiểm tra các app mới được định tuyến bằng tên Anh/Việt nhưng vẫn chỉ trả khóa cố định."""
    commands = {
        "Mở Microsoft Edge": "edge",
        "Mở trình quản lý tệp": "file_explorer",
        "Mở Notepad": "notepad",
        "Mở Calculator": "calculator",
        "Mở Paint": "paint",
        "Mở Windows Terminal": "terminal",
        "Mở cài đặt Windows": "settings",
        "Mở Spotify": "spotify",
        "Mở công cụ chụp màn hình": "snipping_tool",
    }

    for command, expected_key in commands.items():
        intent = make_router().route(command)
        assert intent.kind is IntentType.OPEN_APP
        assert intent.arguments == {"app": expected_key}


def test_routes_model_before_generic_open_app() -> None:
    """Kiểm tra tên model không bị hiểu nhầm thành ứng dụng."""
    intent = make_router().route("Hiện Rasengan")
    assert intent.kind is IntentType.SELECT_MODEL
    assert intent.arguments["model_key"] == "rasengan"


def test_routes_model_focus_without_reopening_it() -> None:
    """Kiểm tra lệnh chọn model được tách khỏi lệnh tạo hologram mới."""
    commands = (
        "Chọn Rasengan",
        "Điều khiển Minato Kunai",
        "Select Iron Man Mask",
    )
    expected = ("rasengan", "minato_kunai", "iron_man_mask")

    for command, model_key in zip(commands, expected, strict=True):
        intent = make_router().route(command)
        assert intent.kind is IntentType.FOCUS_MODEL
        assert intent.arguments == {"model_key": model_key}


def test_routes_named_model_zoom_percentage_locally() -> None:
    """Kiểm tra phóng to model có tên và phần trăm không bị hiểu thành mở model."""
    intent = make_router().route("Phóng to Rasengan 30%")

    assert intent.kind is IntentType.MODEL_ZOOM
    assert intent.arguments == {
        "operation": "in",
        "percent": 30,
        "model_key": "rasengan",
    }


def test_routes_selected_model_shrink_with_visible_default() -> None:
    """Kiểm tra lệnh thu nhỏ không nêu số dùng bước 30% đủ rõ cho model đang chọn."""
    intent = make_router().route("Thu nhỏ model đang chọn")

    assert intent.kind is IntentType.MODEL_ZOOM
    assert intent.arguments == {"operation": "out", "percent": 30}


def test_bare_zoom_command_defaults_to_zoom_in() -> None:
    """Kiểm tra transcript ngắn `zoom model` vẫn phóng to thay vì rơi sang chat cloud."""
    intent = make_router().route("Zoom model")

    assert intent.kind is IntentType.MODEL_ZOOM
    assert intent.arguments == {"operation": "in", "percent": 30}


def test_model_zoom_percentage_is_bounded() -> None:
    """Kiểm tra phần trăm quá lớn bị giới hạn để hologram không biến mất khỏi viewport."""
    intent = make_router().route("Zoom out Minato Kunai 500%")

    assert intent.kind is IntentType.MODEL_ZOOM
    assert intent.arguments["percent"] == 100


def test_routes_google_search() -> None:
    """Kiểm tra truy vấn web được trích xuất khỏi câu tiếng Việt cũ để tương thích."""
    intent = make_router().route("Tìm kiếm Google mechatronics project ideas")
    assert intent.kind is IntentType.GOOGLE_SEARCH
    assert intent.arguments["query"] == "mechatronics project ideas"


def test_routes_explicit_research_phrases_without_cloud_classification() -> None:
    """Kiểm tra các câu tra cứu rõ ràng đi thẳng tới Web Search có kiểm soát."""
    expected = {
        "Tra cứu robot hình người mới nhất": "robot hình người mới nhất",
        "Tìm thông tin về kính AR": "kính AR",
        "Latest information": None,
    }

    for command, query in expected.items():
        intent = make_router().route(command)
        if query is None:
            assert intent.kind is IntentType.GENERAL_CHAT
        else:
            assert intent.kind is IntentType.GOOGLE_SEARCH
            assert intent.arguments["query"] == query


def test_routes_mixed_language_search_and_dropped_keyword_to_research() -> None:
    """Kiểm tra Web Search vẫn mở panel khi STT làm mất từ `search` đầu câu."""
    expected = {
        "Search thông tin về VN Thái Lan": "VN Thái Lan",
        "Searching information about Vietnam Thailand": "Vietnam Thailand",
        "Thông tin về Việt Nam Thái Lan": "Việt Nam Thái Lan",
        "Bạn hãy search thông tin về Việt Nam Thái Lan": "Việt Nam Thái Lan",
        "Cho mình tra cứu trận Việt Nam Thái Lan": "trận Việt Nam Thái Lan",
    }

    for command, query in expected.items():
        intent = make_router().route(command)
        assert intent.kind is IntentType.GOOGLE_SEARCH
        assert intent.arguments["query"] == query


def test_explicit_research_wins_over_short_model_selection() -> None:
    """Kiểm tra yêu cầu thông tin về model mở bảng nguồn thay vì spawn model 3D."""
    intent = make_router().route("Thông tin về Rasengan")

    assert intent.kind is IntentType.GOOGLE_SEARCH
    assert intent.arguments == {"query": "Rasengan"}


def test_routes_close_research_panel_locally() -> None:
    """Kiểm tra lệnh đóng thông tin không bị gửi lên API hoặc đóng model 3D."""
    for command in ("Đóng thông tin", "tắt thông tin", "close research"):
        assert make_router().route(command).kind is IntentType.CLOSE_RESEARCH

    close_all = make_router().route("Đóng tất cả thông tin")
    assert close_all.kind is IntentType.CLOSE_RESEARCH
    assert close_all.arguments == {"all": True}


def test_routes_volume() -> None:
    """Kiểm tra thao tác âm lượng được xử lý local."""
    intent = make_router().route("giảm âm lượng 4")
    assert intent.kind is IntentType.VOLUME
    assert intent.arguments == {"operation": "down", "steps": 4}


def test_routes_relative_volume_percentage_without_converting_it_to_steps() -> None:
    """Kiểm tra giảm 30% giữ đúng đơn vị phần trăm thay vì thành 20 lần nhấn."""
    commands = ("giảm âm lượng đi 30%", "giảm âm lượng 30 phần trăm")

    for command in commands:
        intent = make_router().route(command)
        assert intent.kind is IntentType.VOLUME
        assert intent.arguments == {"operation": "down", "percent": 30}


def test_bare_volume_percentage_means_target_level() -> None:
    """Kiểm tra câu không có hướng tăng/giảm được hiểu là đặt mức âm lượng đích."""
    intent = make_router().route("âm lượng 30%")

    assert intent.kind is IntentType.VOLUME
    assert intent.arguments == {"operation": "set", "percent": 30}


def test_routes_bilingual_model_close_commands() -> None:
    """Kiểm tra các biến thể đóng hologram được xử lý local, kể cả dấu câu."""
    commands = (
        "end",
        "End.",
        "ending session",
        "Ending session.",
        "kết thúc",
        "Kết thúc phiên!",
        "đóng hologram",
    )

    for command in commands:
        assert make_router().route(command).kind is IntentType.CLOSE_MODEL


def test_named_close_command_wins_over_short_model_selection() -> None:
    """Đảm bảo `Close + tên model` đóng panel thay vì vô tình mở lại model đó."""
    commands = (
        "Close Rasengan",
        "Close Iron Man Mask.",
        "Đóng Minato Kunai",
        "Tắt Rasengan",
        "Close the misheard model name",
    )

    for command in commands:
        intent = make_router().route(command)
        assert intent.kind is IntentType.CLOSE_MODEL


def test_named_close_command_identifies_only_the_requested_floating_model() -> None:
    """Kiểm tra lệnh đóng có tên mang khóa model để không xóa các hologram còn lại."""
    intent = make_router().route("Close Rasengan")

    assert intent.kind is IntentType.CLOSE_MODEL
    assert intent.arguments == {"model_key": "rasengan"}


def test_end_session_closes_all_floating_models() -> None:
    """Kiểm tra `end` kết thúc toàn bộ phiên nhiều model thay vì chỉ model đang chọn."""
    intent = make_router().route("Kết thúc phiên")

    assert intent.kind is IntentType.CLOSE_MODEL
    assert intent.arguments == {"all": True}


def test_mute_command_is_not_mistaken_for_model_close() -> None:
    """Đảm bảo ưu tiên động từ `tắt` không biến yêu cầu tắt tiếng thành đóng hologram."""
    intent = make_router().route("Tắt tiếng")

    assert intent.kind is IntentType.VOLUME
    assert intent.arguments["operation"] == "mute"


def test_routes_guard_commands_before_cloud_or_model_actions() -> None:
    """Kiểm tra bật/tắt/trạng thái sonar luôn được xử lý local không tốn API."""
    expected = {
        "trạng thái sonar": IntentType.ARM_GUARD,
        "trạng thái của Sona": IntentType.ARM_GUARD,
        "bật chế độ Sonna": IntentType.ARM_GUARD,
        "tắt sonar": IntentType.DISARM_GUARD,
        "tắt Sona": IntentType.DISARM_GUARD,
        "sonar đang thế nào": IntentType.GUARD_STATUS,
    }

    for command, intent_type in expected.items():
        assert make_router().route(command).kind is intent_type


def test_routes_shutdown_aris_as_a_local_intent() -> None:
    """Kiểm tra lệnh tắt ARIS không bị gửi tới cloud hoặc hiểu nhầm là đóng model."""
    for command in ("Tắt ARIS", "shutdown ARIS", "close ARIS"):
        assert make_router().route(command).kind is IntentType.EXIT_ARIS

    confirmed = make_router().route("Xác nhận tắt ARIS")
    assert confirmed.kind is IntentType.EXIT_ARIS
    assert confirmed.arguments["confirmed"] is True


def test_routes_broad_explicit_shutdown_vocabulary_without_cloud() -> None:
    """Kiểm tra các cách nói Việt–Anh và tên ARIS nghe lệch vẫn tắt trực tiếp."""
    commands = (
        "Đóng ứng dụng ARIS lại",
        "Cho ARIS ngừng hoạt động",
        "ARIS dừng lại đi",
        "Kết thúc chương trình ARIS",
        "Power down ARIS",
        "Terminate Iris",
        "Please shut the ARIS app down",
    )

    for command in commands:
        intent = make_router().route(command)
        assert intent.kind is IntentType.EXIT_ARIS, command
        assert intent.arguments == {"confirmed": True}, command


def test_routes_natural_bilingual_paraphrases_locally() -> None:
    """Kiểm tra lời nói lịch sự và đồng nghĩa Anh–Việt vẫn đi vào action local nhanh."""
    cases = (
        (
            "Could you please bring up the code editor for me?",
            IntentType.OPEN_APP,
            {"app": "vscode"},
        ),
        (
            "Bạn có thể chạy trình duyệt Chrome giúp mình được không?",
            IntentType.OPEN_APP,
            {"app": "chrome"},
        ),
        (
            "I would like you to render the Iron Man Mask on screen",
            IntentType.SELECT_MODEL,
            {"model_key": "iron_man_mask"},
        ),
        (
            "Vui lòng gọi Rasengan ra cho mình xem",
            IntentType.SELECT_MODEL,
            {"model_key": "rasengan"},
        ),
        (
            "Please switch to the Web Shooter",
            IntentType.FOCUS_MODEL,
            {"model_key": "web_shooter"},
        ),
        (
            "Make Rasengan larger by 45 percent",
            IntentType.MODEL_ZOOM,
            {"operation": "in", "percent": 45, "model_key": "rasengan"},
        ),
        (
            "Make it quieter by 20 percent",
            IntentType.VOLUME,
            {"operation": "down", "percent": 20},
        ),
        (
            "Please locate the file portfolio.pdf",
            IntentType.OPEN_FILE,
            {"query": "portfolio.pdf"},
        ),
        ("Could you create a hand model", IntentType.SCAN_HAND, {}),
        ("Please quit ARIS", IntentType.EXIT_ARIS, {"confirmed": True}),
    )

    for command, expected_kind, expected_arguments in cases:
        intent = make_router().route(command)
        assert intent.kind is expected_kind, command
        assert intent.arguments == expected_arguments, command


def test_routes_more_natural_music_and_search_phrases() -> None:
    """Kiểm tra câu nghe nhạc và tra cứu tự nhiên giữ đúng nội dung cần truyền đi."""
    music = make_router().route("Please listen to song Nơi này có anh")
    search = make_router().route("Could you research humanoid robots for me")

    assert music.kind is IntentType.PLAY_MUSIC
    assert music.arguments == {"query": "noi nay co anh"}
    assert search.kind is IntentType.GOOGLE_SEARCH
    assert search.arguments == {"query": "humanoid robots for me"}


def test_negated_hypothetical_and_quoted_commands_do_not_execute_locally() -> None:
    """Đảm bảo câu phủ định hoặc nhắc ví dụ được AI hiểu ngữ cảnh trước khi có side effect."""
    commands = (
        "Don't open Chrome",
        "Đừng tắt ARIS",
        "What happens if I close Rasengan?",
        'Repeat the phrase "open Discord"',
        "Tôi không muốn đóng ARIS",
        "Bạn đừng tắt ARIS nhé",
        "I really don't want you to close Chrome",
    )

    for command in commands:
        intent = make_router().route(command)
        assert intent.kind is IntentType.GENERAL_CHAT
