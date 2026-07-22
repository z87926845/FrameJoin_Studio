from __future__ import annotations

import tempfile
from pathlib import Path

from .models import MediaClip


def _ffconcat_escape(path: str) -> str:
    value = str(Path(path).resolve()).replace("\\", "/")
    return value.replace("'", "'\\''")


def build_ffconcat(clips: list[MediaClip], use_ranges: bool = True) -> Path:
    temp = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", suffix=".ffconcat",
        prefix="framejoin_", delete=False,
    )
    with temp:
        temp.write("ffconcat version 1.0\n")
        for clip in clips:
            temp.write(f"file '{_ffconcat_escape(clip.path)}'\n")
            if use_ranges:
                if clip.start_seconds > 0:
                    temp.write(f"inpoint {clip.start_seconds:.9f}\n")
                temp.write(f"outpoint {clip.end_seconds:.9f}\n")
    return Path(temp.name)
