from __future__ import annotations

from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any
from uuid import uuid4


def parse_fraction(value: str | None) -> Fraction:
    if not value or value in {"0/0", "N/A"}:
        return Fraction(0, 1)
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError):
        try:
            return Fraction(float(value)).limit_denominator(100_000)
        except (ValueError, TypeError, ZeroDivisionError):
            return Fraction(0, 1)


@dataclass(slots=True)
class MediaClip:
    path: str
    clip_id: str = field(default_factory=lambda: uuid4().hex)
    media_type: str = "video"  # video | sequence
    codec: str = "unknown"
    codec_long_name: str = ""
    codec_tag: str = ""
    profile: str = ""
    level: int = 0
    width: int = 0
    height: int = 0
    coded_width: int = 0
    coded_height: int = 0
    rotation: int = 0
    pix_fmt: str = ""
    field_order: str = ""
    color_range: str = ""
    color_space: str = ""
    color_transfer: str = ""
    color_primaries: str = ""
    chroma_location: str = ""
    fps_num: int = 0
    fps_den: int = 1
    source_r_fps: float = 0.0
    source_avg_fps: float = 0.0
    time_base_num: int = 0
    time_base_den: int = 1
    duration: float = 0.0
    total_frames: int = 0
    is_vfr: bool = False
    bit_rate: int = 0
    file_size: int = 0
    format_name: str = ""
    source_timecode: str = ""
    stream_signature: list[str] = field(default_factory=list)
    has_audio: bool = False
    audio_codec: str = ""
    audio_profile: str = ""
    audio_sample_rate: int = 0
    audio_channels: int = 0
    audio_sample_fmt: str = ""
    audio_channel_layout: str = ""
    start_frame: int = 0
    end_frame: int = 0

    # Image-sequence metadata. sequence_end_number is inclusive.
    sequence_pattern: str = ""
    sequence_start_number: int = 0
    sequence_end_number: int = 0
    sequence_digits: int = 0
    sequence_prefix: str = ""
    sequence_suffix: str = ""
    sequence_missing_count: int = 0
    sequence_missing_preview: list[int] = field(default_factory=list)
    sequence_actual_files: int = 0
    has_alpha: bool = False

    # Per-clip colour treatment.
    lut_path: str = ""
    lut_interp: str = "tetrahedral"
    lut_strength: float = 1.0

    @property
    def name(self) -> str:
        if self.media_type == "sequence" and self.sequence_pattern:
            return Path(self.sequence_pattern).name
        return Path(self.path).name

    @property
    def type_label(self) -> str:
        return "序列帧" if self.media_type == "sequence" else "视频"

    @property
    def fps(self) -> float:
        if self.fps_den == 0:
            return 0.0
        return self.fps_num / self.fps_den

    def set_fps_value(self, fps: str | float | Fraction) -> None:
        if isinstance(fps, Fraction):
            fraction = fps
        elif isinstance(fps, str):
            fraction = parse_fraction(fps.strip())
        else:
            try:
                fraction = Fraction(float(fps)).limit_denominator(100_000)
            except (TypeError, ValueError, ZeroDivisionError):
                fraction = Fraction(0, 1)
        if fraction <= 0:
            raise ValueError("帧率必须大于 0")
        fraction = fraction.limit_denominator(100_000)
        self.fps_num = fraction.numerator
        self.fps_den = fraction.denominator
        self.source_r_fps = float(fraction)
        self.source_avg_fps = float(fraction)
        if self.total_frames > 0:
            self.duration = self.total_frames / float(fraction)

    def set_fps(self, fps: float) -> None:
        self.set_fps_value(fps)

    @property
    def fps_expression(self) -> str:
        if self.fps_num <= 0 or self.fps_den <= 0:
            return "0"
        if self.fps_den == 1:
            return str(self.fps_num)
        return f"{self.fps_num}/{self.fps_den}"

    @property
    def fps_display(self) -> str:
        expression = self.fps_expression
        if self.fps_den == 1:
            return f"{self.fps:.3f}"
        return f"{expression} ({self.fps:.3f})"

    @property
    def time_base(self) -> str:
        return f"{self.time_base_num}/{self.time_base_den}" if self.time_base_num else "未知"

    @property
    def resolution(self) -> str:
        return f"{self.width}×{self.height}" if self.width and self.height else "未知"

    @property
    def bit_depth(self) -> int:
        value = self.pix_fmt.lower()
        for depth in (16, 14, 12, 10, 9):
            if str(depth) in value:
                return depth
        return 8 if value else 0

    @property
    def bitrate_mbps(self) -> float:
        return self.bit_rate / 1_000_000 if self.bit_rate > 0 else 0.0

    @property
    def kept_frames(self) -> int:
        return max(0, self.end_frame - self.start_frame)

    @property
    def start_seconds(self) -> float:
        return self.start_frame / self.fps if self.fps > 0 else 0.0

    @property
    def end_seconds(self) -> float:
        if self.fps <= 0:
            return self.duration
        return min(self.end_frame / self.fps, self.duration or float("inf"))

    @property
    def kept_duration(self) -> float:
        if self.fps <= 0:
            return max(0.0, self.end_seconds - self.start_seconds)
        return self.kept_frames / self.fps

    @property
    def sequence_is_complete(self) -> bool:
        return self.media_type != "sequence" or self.sequence_missing_count == 0

    def sequence_file_for_frame(self, frame_index: int) -> str:
        if self.media_type != "sequence":
            return self.path
        number = self.sequence_start_number + max(0, int(frame_index))
        filename = f"{self.sequence_prefix}{number:0{self.sequence_digits}d}{self.sequence_suffix}"
        return str(Path(self.path).parent / filename)

    def normalize_range(self) -> None:
        maximum = max(0, self.total_frames)
        self.start_frame = max(0, min(int(self.start_frame), maximum))
        requested_end = int(self.end_frame) if self.end_frame else maximum
        self.end_frame = max(self.start_frame, min(requested_end, maximum))

    def reset_full_range(self) -> None:
        self.start_frame = 0
        self.end_frame = max(0, self.total_frames)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MediaClip":
        valid = {item.name for item in cls.__dataclass_fields__.values()}
        clip = cls(**{key: value for key, value in data.items() if key in valid})
        clip.normalize_range()
        return clip


@dataclass(slots=True)
class JoinSettings:
    container: str = "auto"  # video: auto/copy container; encoded output: mp4/mov/mkv
    faststart: bool = True

    # Image-sequence output.
    sequence_output_mode: str = "video"  # video | frames
    sequence_codec: str = "h264_lossless"  # h264_lossless | h265_lossless | ffv1
    sequence_bitrate_enabled: bool = False
    sequence_bitrate_mbps: int = 100
    sequence_encoder_backend: str = "auto"  # auto | cpu | nvenc | qsv | amf | videotoolbox
    sequence_frame_prefix: str = "frame_"
    sequence_frame_start: int = 1
    sequence_frame_digits: int = 6

    # Video output. Stream copy remains the default.
    video_transcode_enabled: bool = False
    video_codec: str = "h264"  # h264 | h265
    video_bitrate_mbps: int = 100
    video_encoder_backend: str = "auto"
    video_fps_mode: str = "source"  # source | custom
    video_fps: str = "24"
    video_audio_mode: str = "aac"  # aac | copy | none

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JoinSettings":
        valid = {item.name for item in cls.__dataclass_fields__.values()}
        return cls(**{key: value for key, value in data.items() if key in valid})
