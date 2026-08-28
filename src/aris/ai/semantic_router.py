from __future__ import annotations

import json
from typing import Any

from aris.ai.router import IntentRouter, _plain
from aris.core.types import Intent, IntentType
from aris.models.catalog import ModelCatalog

SEMANTIC_ACTION_TOOL: dict[str, object] = {
    "type": "function",
    "name": "execute_aris_action",
    "description": (
        "Map a direct English or Vietnamese user command to exactly one safe ARIS action. "
        "Never call this for ordinary questions or conversation. Use canonical app/model keys."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "open_app",
                    "close_app",
                    "show_model",
                    "focus_model",
                    "close_model",
                    "close_all_models",
                    "zoom_model",
                    "open_file",
                    "web_search",
                    "close_research",
                    "close_all_research",
                    "play_music",
                    "pause_music",
                    "resume_music",
                    "stop_music",
                    "music_volume",
                    "system_volume",
                    "scan_hand",
                    "arm_guard",
                    "disarm_guard",
                    "guard_status",
                    "exit_aris",
                    "help",
                ],
            },
            "target": {
                "type": ["string", "null"],
                "description": (
                    "Canonical app/model key, file name, search query, or song title. "
                    "Use null when the action has no target."
                ),
            },
            "operation": {
                "type": ["string", "null"],
                "enum": ["in", "out", "up", "down", "set", "mute", None],
            },
            "amount": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
            "unit": {
                "type": ["string", "null"],
                "enum": ["percent", "steps", None],
            },
        },
        "required": ["action", "target", "operation", "amount", "unit"],
        "additionalProperties": False,
    },
}


def parse_semantic_arguments(arguments: str | dict[str, Any]) -> dict[str, Any] | None:
    """Đọc JSON function call và chỉ nhận object phẳng để lớp sau tiếp tục kiểm tra."""
    try:
        parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def intent_from_semantic_arguments(
    arguments: str | dict[str, Any],
    catalog: ModelCatalog,
) -> Intent | None:
    """Ánh xạ function call AI vào Intent cố định; giá trị ngoài allowlist bị từ chối."""
    data = parse_semantic_arguments(arguments)
    if data is None:
        return None
    action = str(data.get("action") or "").strip().casefold()
    target = str(data.get("target") or "").strip()[:500]
    operation = str(data.get("operation") or "").strip().casefold()
    amount = _bounded_amount(data.get("amount"))
    unit = str(data.get("unit") or "").strip().casefold()

    if action == "open_app":
        app_key = _canonical_app_key(target)
        return Intent(IntentType.OPEN_APP, {"app": app_key}) if app_key else None
    if action == "close_app":
        app_key = _canonical_app_key(target)
        return Intent(IntentType.CLOSE_APP, {"app": app_key}) if app_key else None
    if action in {"show_model", "focus_model"}:
        model_key = _canonical_model_key(target, catalog)
        if model_key is None:
            return None
        kind = IntentType.SELECT_MODEL if action == "show_model" else IntentType.FOCUS_MODEL
        return Intent(kind, {"model_key": model_key})
    if action == "close_model":
        if not target:
            return Intent(IntentType.CLOSE_MODEL)
        model_key = _canonical_model_key(target, catalog)
        return Intent(IntentType.CLOSE_MODEL, {"model_key": model_key}) if model_key else None
    if action == "close_all_models":
        return Intent(IntentType.CLOSE_MODEL, {"all": True})
    if action == "zoom_model":
        if operation not in {"in", "out"}:
            return None
        arguments_out: dict[str, object] = {
            "operation": operation,
            "percent": max(1, amount or 30),
        }
        if target:
            model_key = _canonical_model_key(target, catalog)
            if model_key is None:
                return None
            arguments_out["model_key"] = model_key
        return Intent(IntentType.MODEL_ZOOM, arguments_out)
    if action == "open_file" and target:
        return Intent(IntentType.OPEN_FILE, {"query": target})
    if action == "web_search" and target:
        return Intent(IntentType.GOOGLE_SEARCH, {"query": target})
    if action == "close_research":
        return Intent(IntentType.CLOSE_RESEARCH)
    if action == "close_all_research":
        return Intent(IntentType.CLOSE_RESEARCH, {"all": True})
    if action == "play_music":
        return Intent(IntentType.PLAY_MUSIC, {"query": target})
    if action == "pause_music":
        return Intent(IntentType.PAUSE_MUSIC)
    if action == "resume_music":
        return Intent(IntentType.RESUME_MUSIC)
    if action == "stop_music":
        return Intent(IntentType.STOP_MUSIC)
    if action == "music_volume":
        if operation not in {"up", "down", "set"}:
            return None
        return Intent(
            IntentType.MUSIC_VOLUME,
            {"operation": operation, "percent": amount if amount is not None else 10},
        )
    if action == "system_volume":
        return _system_volume_intent(operation, amount, unit)
    fixed_actions = {
        "scan_hand": IntentType.SCAN_HAND,
        "arm_guard": IntentType.ARM_GUARD,
        "disarm_guard": IntentType.DISARM_GUARD,
        "guard_status": IntentType.GUARD_STATUS,
        "exit_aris": IntentType.EXIT_ARIS,
        "help": IntentType.HELP,
    }
    kind = fixed_actions.get(action)
    return Intent(kind) if kind is not None else None


def _canonical_app_key(target: str) -> str | None:
    """Đổi tên app tự nhiên sang khóa allowlist và không trả đường dẫn hay tham số lệnh."""
    normalized = _plain(target)
    allowed_keys = set(IntentRouter.APP_ALIASES.values())
    if normalized in allowed_keys:
        return normalized
    return IntentRouter.APP_ALIASES.get(normalized)


def _canonical_model_key(target: str, catalog: ModelCatalog) -> str | None:
    """Đổi tên model song ngữ hoặc khóa canonical sang một model có thật trong catalog."""
    normalized = _plain(target).replace(" ", "_")
    try:
        return catalog.get(normalized).key
    except KeyError:
        matched = catalog.match(target)
        if matched is not None:
            return matched.key
    plain_target = _plain(target)
    for spec in catalog.all():
        if plain_target in {_plain(spec.display_name), _plain(spec.short_name_vi)}:
            return spec.key
    return None


def _bounded_amount(value: object) -> int | None:
    """Chuyển amount sang số nguyên 0–100 hoặc trả None khi AI gửi kiểu không hợp lệ."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return None


def _system_volume_intent(operation: str, amount: int | None, unit: str) -> Intent | None:
    """Tạo volume intent đúng đơn vị để không lặp lại lỗi 30% bị hiểu thành số bước."""
    if operation == "mute":
        return Intent(IntentType.VOLUME, {"operation": "mute", "steps": 1})
    if operation not in {"up", "down", "set"}:
        return None
    value = amount if amount is not None else (3 if unit == "steps" else 10)
    key = "steps" if unit == "steps" and operation != "set" else "percent"
    return Intent(IntentType.VOLUME, {"operation": operation, key: value})
