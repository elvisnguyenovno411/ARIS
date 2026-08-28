from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Mô tả metadata và cách đặt một model trong thư viện ARIS."""

    key: str
    display_name: str
    short_name_vi: str
    description: str
    description_vi: str
    placement: str
    accent: str


MODEL_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        "iron_man_mask",
        "Iron Man Mask",
        "Mặt nạ Iron Man",
        "A segmented low-poly helmet study.",
        "Mẫu mũ low-poly ghép từ nhiều mảng.",
        "standalone",
        "gold",
    ),
    ModelSpec(
        "iron_man_hand",
        "Iron Man Hand",
        "Bàn tay Iron Man",
        "A palm-mounted armor and energy emitter concept.",
        "Giáp bàn tay và bộ phát năng lượng lòng bàn tay.",
        "hand",
        "red",
    ),
    ModelSpec(
        "spider_man_mask",
        "Spider-Man Mask",
        "Mặt nạ Spider-Man",
        "A web-patterned low-poly mask study.",
        "Mẫu mặt nạ low-poly với họa tiết mạng nhện.",
        "standalone",
        "red",
    ),
    ModelSpec(
        "web_shooter",
        "Web Shooter",
        "Máy bắn tơ",
        "A compact wrist-mounted mechanical launcher.",
        "Thiết bị phóng cơ khí nhỏ gắn trên cổ tay.",
        "wrist",
        "silver",
    ),
    ModelSpec(
        "rasengan",
        "Rasengan",
        "Rasengan",
        "A layered rotating energy sphere.",
        "Quả cầu năng lượng nhiều lớp đang xoay.",
        "palm",
        "cyan",
    ),
    ModelSpec(
        "minato_kunai",
        "Minato Kunai",
        "Kunai Minato",
        "A tri-point low-poly kunai concept.",
        "Mẫu kunai ba mũi dạng low-poly.",
        "grip",
        "violet",
    ),
)


class ModelCatalog:
    """Cung cấp truy cập ổn định đến sáu model beta và các tên đồng nghĩa."""

    def __init__(self) -> None:
        """Tạo chỉ mục model theo khóa và tên tìm kiếm song ngữ."""
        self._by_key = {item.key: item for item in MODEL_SPECS}
        self._aliases = {
            "iron man mask": "iron_man_mask",
            "mặt nạ iron man": "iron_man_mask",
            "ironman mask": "iron_man_mask",
            "iron man hand": "iron_man_hand",
            "iron man gauntlet": "iron_man_hand",
            "bàn tay iron man": "iron_man_hand",
            "spider man mask": "spider_man_mask",
            "spider-man mask": "spider_man_mask",
            "mặt nạ spiderman": "spider_man_mask",
            "mặt nạ spider man": "spider_man_mask",
            "web shooter": "web_shooter",
            "máy bắn tơ": "web_shooter",
            "rasengan": "rasengan",
            "quả cầu năng lượng": "rasengan",
            "energy sphere": "rasengan",
            "minato kunai": "minato_kunai",
            "kunai minato": "minato_kunai",
            "kunai": "minato_kunai",
        }

    def all(self) -> tuple[ModelSpec, ...]:
        """Trả về toàn bộ model theo thứ tự hiển thị đã định nghĩa."""
        return MODEL_SPECS

    def get(self, key: str) -> ModelSpec:
        """Trả về model theo khóa; phát sinh KeyError nếu khóa không tồn tại."""
        return self._by_key[key]

    def match(self, text: str) -> ModelSpec | None:
        """Tìm model được nhắc đến trong câu tiếng Anh hoặc tiếng Việt."""
        normalized = " ".join(text.casefold().replace("_", " ").split())
        matches = [(alias, key) for alias, key in self._aliases.items() if alias in normalized]
        if not matches:
            return None
        _, key = max(matches, key=lambda pair: len(pair[0]))
        return self._by_key[key]
