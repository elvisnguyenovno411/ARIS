from __future__ import annotations

from aris.core.config import AppConfig


def run_probe() -> int:
    """Gửi một yêu cầu chữ tối thiểu để xác nhận API mà không in hoặc lưu API key."""
    config = AppConfig.load()
    if not config.api_enabled:
        print("ARIS_API_PROBE disabled=true reason=missing_key_or_opt_in")
        return 2

    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.openai_api_key, timeout=30.0, max_retries=1)
        response = client.responses.create(
            model=config.openai_model,
            instructions="Reply with exactly ARIS_API_OK and no other text.",
            input="Check this ARIS project API connection.",
            max_output_tokens=32,
            store=False,
        )
        text = (response.output_text or "").strip()
        if text == "ARIS_API_OK":
            print(f"ARIS_API_PROBE ok model={config.openai_model}")
            return 0
        print("ARIS_API_PROBE failed reason=unexpected_response")
        return 1
    except Exception as error:
        print(f"ARIS_API_PROBE failed error={type(error).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run_probe())
