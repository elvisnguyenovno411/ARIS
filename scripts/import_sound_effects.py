from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "assets" / "user_audio"


def find_ffmpeg() -> Path:
    """Tìm ffmpeg trong PATH hoặc thư mục WinGet phổ biến trên Windows."""
    direct = shutil.which("ffmpeg")
    if direct:
        return Path(direct)
    local_app_data = Path(os.getenv("LOCALAPPDATA", ""))
    candidates = sorted(
        local_app_data.glob(
            "Microsoft/WinGet/Packages/Gyan.FFmpeg_*/ffmpeg-*-full_build/bin/ffmpeg.exe"
        )
    )
    if candidates:
        return candidates[-1]
    raise FileNotFoundError("ffmpeg was not found. Install it with WinGet before importing audio.")


def extract_wav(
    ffmpeg: Path,
    source: Path,
    output: Path,
    start_seconds: float,
    duration_seconds: float,
    volume: float,
) -> None:
    """Cắt một cue WAV PCM có fade từ file nguồn mà không gọi qua shell."""
    output.parent.mkdir(parents=True, exist_ok=True)
    fade_out_start = max(0.0, duration_seconds - 0.35)
    audio_filter = (
        "afade=t=in:st=0:d=0.08,"
        f"afade=t=out:st={fade_out_start:.3f}:d=0.35,"
        f"volume={volume:.3f}"
    )
    subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-t",
            f"{duration_seconds:.3f}",
            "-i",
            str(source),
            "-af",
            audio_filter,
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(output),
        ],
        check=True,
    )


def main() -> int:
    """Tạo cue startup và model-spawn local, giữ chúng ngoài Git vì chưa rõ giấy phép."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("source", type=Path, help="Source MP3/WAV containing the UI sound pack")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    ffmpeg = find_ffmpeg()
    output_dir = args.output_dir.expanduser().resolve()
    extract_wav(ffmpeg, source, output_dir / "startup_local.wav", 4.45, 4.40, 0.70)
    extract_wav(ffmpeg, source, output_dir / "model_spawn_local.wav", 24.05, 1.35, 0.62)
    print(f"SOUND_IMPORT ok output={output_dir} files=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
