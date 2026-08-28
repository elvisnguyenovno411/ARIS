from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from import_spider_mask import simplify_stl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "user_models" / "web_shooter_local.npz"


def import_web_shooter(source: Path, output: Path, target_faces: int = 8_000) -> Path:
    """Giảm polygon, xoay Web Shooter về hướng HUD và lưu NPZ local đã Git-ignore."""
    if not source.is_file():
        raise FileNotFoundError(f"Missing Web Shooter STL: {source}")
    vertices, faces, source_faces = simplify_stl(source, target_faces)
    # STL dài theo Y và dẹt theo Z; quay X 90° để thiết bị nằm dọc khi camera nhìn theo Y.
    oriented = vertices[:, (0, 2, 1)].copy()
    oriented[:, 1] *= -1.0
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        vertices=np.ascontiguousarray(oriented, dtype=np.float32),
        faces=np.ascontiguousarray(faces, dtype=np.int32),
        source_faces=np.asarray([source_faces], dtype=np.int64),
    )
    print(
        f"WEB_SHOOTER_IMPORT ok source_faces={source_faces} "
        f"optimized_faces={len(faces)} output={output}"
    )
    return output


def main() -> int:
    """Đọc tham số CLI và tạo Web Shooter low-poly local cho ARIS."""
    parser = argparse.ArgumentParser(description="Import a local Web Shooter STL into ARIS.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--target-faces", type=int, default=8_000)
    arguments = parser.parse_args()
    import_web_shooter(
        arguments.source.resolve(),
        arguments.output.resolve(),
        arguments.target_faces,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
