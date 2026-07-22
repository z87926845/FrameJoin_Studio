from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def configure_hidden_qprocess(process) -> None:
    """Prevent console FFmpeg/ffprobe programs from flashing a black window on Windows."""
    if sys.platform != "win32" or not hasattr(process, "setCreateProcessArgumentsModifier"):
        return

    def modifier(arguments) -> None:
        try:
            arguments.flags |= CREATE_NO_WINDOW
        except Exception:
            pass

    try:
        process._framejoin_create_process_modifier = modifier
    except Exception:
        pass
    try:
        process.setCreateProcessArgumentsModifier(modifier)
    except Exception:
        pass


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resolve_binary(base_name: str) -> str | None:
    suffix = ".exe" if sys.platform == "win32" else ""
    candidates = [
        app_root() / "tools" / f"{base_name}{suffix}",
        app_root() / f"{base_name}{suffix}",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which(base_name) or shutil.which(f"{base_name}{suffix}")


@dataclass(slots=True)
class Toolchain:
    ffmpeg: str | None
    ffprobe: str | None
    ffmpeg_vvc: str | None = None
    ffprobe_vvc: str | None = None
    mpv: str | None = None
    ffplay: str | None = None

    @classmethod
    def detect(cls) -> "Toolchain":
        return cls(
            ffmpeg=resolve_binary("ffmpeg"),
            ffprobe=resolve_binary("ffprobe"),
            ffplay=resolve_binary("ffplay"),
        )


@dataclass(slots=True)
class EncoderCapabilities:
    """Compatibility placeholder retained for the shared timeline constructor."""

    encoders: set[str] = field(default_factory=set)
