from __future__ import annotations

import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from dataclasses import dataclass, field
from pathlib import Path


CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def hidden_subprocess_kwargs() -> dict:
    """Return subprocess options that keep console tools invisible on Windows."""
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = startupinfo
    return kwargs


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


_HARDWARE_ENCODERS = {
    "nvenc": {"h264_lossless": "h264_nvenc", "h265_lossless": "hevc_nvenc"},
    "qsv": {"h264_lossless": "h264_qsv", "h265_lossless": "hevc_qsv"},
    "amf": {"h264_lossless": "h264_amf", "h265_lossless": "hevc_amf"},
    "videotoolbox": {"h264_lossless": "h264_videotoolbox", "h265_lossless": "hevc_videotoolbox"},
}

_HARDWARE_LABELS = {
    "auto": "自动选择",
    "cpu": "CPU 软件编码",
    "nvenc": "NVIDIA NVENC",
    "qsv": "Intel Quick Sync",
    "amf": "AMD AMF",
    "videotoolbox": "Apple VideoToolbox",
}


@dataclass(slots=True)
class EncoderCapabilities:
    """FFmpeg encoder names and hardware encoders verified on this machine."""

    encoders: set[str] = field(default_factory=set)
    usable_hardware_encoders: set[str] = field(default_factory=set)
    detection_error: str = ""

    @classmethod
    def detect(cls, ffmpeg_path: str | None) -> "EncoderCapabilities":
        if not ffmpeg_path:
            return cls(set(), set(), "未找到 FFmpeg")
        try:
            completed = subprocess.run(
                [ffmpeg_path, "-hide_banner", "-encoders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
                **hidden_subprocess_kwargs(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return cls(set(), set(), str(exc))
        encoders: set[str] = set()
        for line in completed.stdout.splitlines():
            match = re.match(r"^\s*[A-Z.]{6}\s+(\S+)", line)
            if match:
                encoders.add(match.group(1))
        hardware_names = {
            encoder
            for mapping in _HARDWARE_ENCODERS.values()
            for encoder in mapping.values()
            if encoder in encoders
        }

        def probe_hardware_encoder(encoder_name: str) -> tuple[str, bool]:
            try:
                result = subprocess.run(
                    [
                        ffmpeg_path, "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-f", "lavfi", "-i", "color=c=black:s=64x64:r=1:d=0.1",
                        "-frames:v", "1", "-c:v", encoder_name, "-f", "null", "-",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    check=False,
                    **hidden_subprocess_kwargs(),
                )
                return encoder_name, result.returncode == 0
            except (OSError, subprocess.SubprocessError):
                return encoder_name, False

        usable: set[str] = set()
        if hardware_names:
            with ThreadPoolExecutor(max_workers=min(4, len(hardware_names))) as pool:
                futures = [pool.submit(probe_hardware_encoder, name) for name in sorted(hardware_names)]
                for future in as_completed(futures):
                    name, ok = future.result()
                    if ok:
                        usable.add(name)
        error = "" if encoders else "FFmpeg 未返回编码器列表"
        return cls(encoders, usable, error)

    def supports(self, encoder_name: str) -> bool:
        return encoder_name in self.encoders

    def encoder_for(self, backend: str, codec: str) -> str | None:
        name = _HARDWARE_ENCODERS.get(backend, {}).get(codec)
        return name if name and name in self.usable_hardware_encoders else None

    def backend_available(self, backend: str, codec: str) -> bool:
        if backend in {"auto", "cpu"}:
            return True
        return self.encoder_for(backend, codec) is not None

    def available_hardware_backends(self, codec: str) -> list[str]:
        return [name for name in (("videotoolbox", "nvenc", "qsv", "amf") if sys.platform == "darwin" else ("nvenc", "qsv", "amf", "videotoolbox")) if self.encoder_for(name, codec)]

    @staticmethod
    def backend_label(backend: str) -> str:
        return _HARDWARE_LABELS.get(backend, backend)
