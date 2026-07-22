from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

from .models import JoinSettings, MediaClip
from .preview import build_ffconcat


@dataclass(slots=True)
class ExportPlan:
    commands: list[list[str]]
    temporary_files: list[Path] = field(default_factory=list)
    encoder: str = ""
    total_duration: float = 0.0
    warnings: list[str] = field(default_factory=list)
    estimated_bytes: int = 0

    @property
    def command(self) -> list[str]:
        return self.commands[0] if self.commands else []


@dataclass(slots=True)
class CompatibilityReport:
    compatible: bool
    differences: list[str]
    summary: str


def _value(value) -> str:
    if isinstance(value, (list, tuple)):
        return "/".join(str(item) for item in value)
    return str(value)


def stream_copy_report(clips: list[MediaClip]) -> CompatibilityReport:
    if not clips:
        return CompatibilityReport(False, ["没有素材"], "尚未载入素材")

    media_types = {clip.media_type for clip in clips}
    if len(media_types) > 1:
        return CompatibilityReport(
            False,
            ["视频与序列帧不能在同一个极速任务中混拼。请分别导出。"],
            "混合素材需要统一解码编码，已为避免暗中转码而拦截",
        )

    if media_types == {"sequence"}:
        first = clips[0]
        differences: list[str] = []
        for index, clip in enumerate(clips, start=1):
            if clip.sequence_missing_count:
                preview = "、".join(str(value) for value in clip.sequence_missing_preview[:12])
                differences.append(
                    f"第{index}段序列缺少 {clip.sequence_missing_count} 帧"
                    + (f"（例如 {preview}）" if preview else "")
                )
        checks = [
            ("分辨率", lambda c: (c.width, c.height)),
            ("输入帧率", lambda c: round(c.fps, 6)),
            ("像素格式/位深", lambda c: c.pix_fmt),
            ("透明通道状态", lambda c: c.has_alpha),
        ]
        for index, clip in enumerate(clips[1:], start=2):
            for label, getter in checks:
                expected = getter(first)
                actual = getter(clip)
                if actual != expected:
                    differences.append(
                        f"第{index}段 {label}不同：第1段={_value(expected)}，第{index}段={_value(actual)}"
                    )
        if differences:
            return CompatibilityReport(False, differences, f"发现 {len(differences)} 项不一致，不能逐帧真无损拼接")
        return CompatibilityReport(
            True, [],
            "序列帧参数一致，可按列表顺序无损转为 H.264、H.265 或 FFV1 视频",
        )

    first = clips[0]
    checks = [
        ("流结构", lambda c: c.stream_signature),
        ("视频编码", lambda c: c.codec),
        ("编码标签", lambda c: c.codec_tag),
        ("Profile", lambda c: c.profile),
        ("Level", lambda c: c.level),
        ("显示分辨率", lambda c: (c.width, c.height)),
        ("编码分辨率", lambda c: (c.coded_width, c.coded_height)),
        ("旋转信息", lambda c: c.rotation % 360),
        ("像素格式/位深", lambda c: c.pix_fmt),
        ("帧率", lambda c: round(c.fps, 6)),
        ("视频时间基", lambda c: c.time_base),
        ("扫描方式", lambda c: c.field_order),
        ("色彩范围", lambda c: c.color_range),
        ("色彩空间", lambda c: c.color_space),
        ("传递特性", lambda c: c.color_transfer),
        ("色彩原色", lambda c: c.color_primaries),
        ("音频存在状态", lambda c: c.has_audio),
        ("音频编码", lambda c: c.audio_codec if c.has_audio else "none"),
        ("音频 Profile", lambda c: c.audio_profile if c.has_audio else "none"),
        ("音频采样率", lambda c: c.audio_sample_rate if c.has_audio else 0),
        ("音频声道数", lambda c: c.audio_channels if c.has_audio else 0),
        ("音频采样格式", lambda c: c.audio_sample_fmt if c.has_audio else "none"),
        ("音频声道布局", lambda c: c.audio_channel_layout if c.has_audio else "none"),
    ]
    differences: list[str] = []
    for index, clip in enumerate(clips[1:], start=2):
        for label, getter in checks:
            expected = getter(first)
            actual = getter(clip)
            if actual != expected:
                differences.append(
                    f"第{index}段 {label}不同：第1段={_value(expected)}，第{index}段={_value(actual)}"
                )
    if differences:
        return CompatibilityReport(False, differences, f"发现 {len(differences)} 项不一致，不能直接原码拼接")
    return CompatibilityReport(True, [], "所有关键流参数一致，可以使用 -c copy 极速无损拼接")


def compatible_for_stream_copy(clips: list[MediaClip]) -> tuple[bool, list[str]]:
    report = stream_copy_report(clips)
    return report.compatible, report.differences


def choose_join_extension(clips: list[MediaClip], settings: JoinSettings) -> str:
    if clips and all(clip.media_type == "sequence" for clip in clips):
        if settings.container in {"mp4", "mov", "mkv"}:
            return settings.container
        return "mp4" if settings.sequence_codec in {"h264_lossless", "h265_lossless"} else "mkv"
    if settings.container != "auto":
        return settings.container
    if not clips:
        return "mkv"
    suffix = Path(clips[0].path).suffix.lower().lstrip(".")
    return suffix if suffix in {"mp4", "mov", "mkv", "mxf", "ts", "m2ts"} else "mkv"


_HARDWARE_ENCODERS = {
    "nvenc": {"h264_lossless": "h264_nvenc", "h265_lossless": "hevc_nvenc"},
    "qsv": {"h264_lossless": "h264_qsv", "h265_lossless": "hevc_qsv"},
    "amf": {"h264_lossless": "h264_amf", "h265_lossless": "hevc_amf"},
    "videotoolbox": {"h264_lossless": "h264_videotoolbox", "h265_lossless": "hevc_videotoolbox"},
}

_BACKEND_LABELS = {
    "cpu": "CPU 软件编码",
    "nvenc": "NVIDIA NVENC",
    "qsv": "Intel Quick Sync",
    "amf": "AMD AMF",
    "videotoolbox": "Apple VideoToolbox",
}


def resolve_sequence_backend(
    codec: str,
    requested: str,
    available_encoders: set[str] | None,
    bit_depth: int,
) -> tuple[str, str | None, list[str]]:
    """Resolve a bitrate-mode encoder backend without changing true-lossless modes."""
    available = available_encoders or set()
    requested = requested if requested in {"auto", "cpu", "nvenc", "qsv", "amf", "videotoolbox"} else "auto"
    notes: list[str] = []

    # Current consumer hardware paths are intentionally limited to <=10-bit HEVC.
    hardware_allowed = not (codec == "h265_lossless" and bit_depth > 10)
    if requested == "cpu":
        return "cpu", None, notes
    if requested != "auto":
        name = _HARDWARE_ENCODERS[requested][codec]
        if not hardware_allowed:
            raise RuntimeError("当前序列超过 10-bit，所选显卡编码路径不能保证正确输出；请改用 CPU 软件编码或 FFV1。")
        if name not in available:
            raise RuntimeError(f"当前 FFmpeg 未提供 {_BACKEND_LABELS[requested]} 编码器（{name}）。")
        return requested, name, notes

    if hardware_allowed:
        backend_order = ("videotoolbox", "nvenc", "qsv", "amf") if sys.platform == "darwin" else ("nvenc", "qsv", "amf", "videotoolbox")
        for backend in backend_order:
            name = _HARDWARE_ENCODERS[backend][codec]
            if name in available:
                return backend, name, notes
    if bit_depth > 10 and codec == "h265_lossless":
        notes.append("当前序列超过 10-bit，自动模式已回退到 CPU 软件编码。")
    elif not available:
        notes.append("未检测到可用显卡编码器，自动模式已回退到 CPU 软件编码。")
    else:
        notes.append("没有与当前编码匹配的显卡编码器，自动模式已回退到 CPU 软件编码。")
    return "cpu", None, notes


def _hardware_bitrate_args(
    backend: str,
    encoder_name: str,
    codec: str,
    bit_depth: int,
    rate: str,
    buffer_size: str,
) -> tuple[list[str], str, list[str]]:
    if backend == "nvenc":
        pixel_format = "yuv420p" if codec == "h264_lossless" or bit_depth <= 8 else "p010le"
        profile = "high" if codec == "h264_lossless" else ("main" if bit_depth <= 8 else "main10")
        args = [
            "-c:v", encoder_name, "-preset", "p6", "-tune", "hq", "-rc", "vbr",
            "-b:v", rate, "-maxrate", rate, "-bufsize", buffer_size,
            "-pix_fmt", pixel_format, "-profile:v", profile,
            "-spatial_aq", "1", "-temporal_aq", "1", "-rc-lookahead", "20",
        ]
    elif backend == "qsv":
        pixel_format = "nv12" if codec == "h264_lossless" or bit_depth <= 8 else "p010le"
        args = [
            "-c:v", encoder_name, "-preset", "slow",
            "-b:v", rate, "-maxrate", rate, "-bufsize", buffer_size,
            "-pix_fmt", pixel_format,
        ]
    elif backend == "amf":
        pixel_format = "nv12" if codec == "h264_lossless" or bit_depth <= 8 else "p010le"
        args = [
            "-c:v", encoder_name, "-usage", "transcoding", "-quality", "quality",
            "-rc", "vbr_peak", "-b:v", rate, "-maxrate", rate, "-bufsize", buffer_size,
            "-pix_fmt", pixel_format,
        ]
    elif backend == "videotoolbox":
        pixel_format = "nv12" if codec == "h264_lossless" or bit_depth <= 8 else "p010le"
        args = [
            "-c:v", encoder_name, "-allow_sw", "1", "-realtime", "0",
            "-b:v", rate, "-maxrate", rate, "-bufsize", buffer_size,
            "-pix_fmt", pixel_format,
        ]
    else:
        raise RuntimeError(f"未知显卡编码后端：{backend}")
    label = _BACKEND_LABELS[backend]
    warnings = [
        f"当前使用 {label} 进行硬件编码；显卡加速只用于目标码流模式，直接真无损模式仍使用 CPU。",
        "硬件编码速度通常更快，但在相同码流下画质可能与 CPU 软件编码略有差异。",
    ]
    return args, label, warnings


def _build_sequence_join_plan(
    clips: list[MediaClip],
    settings: JoinSettings,
    output_path: str,
    ffmpeg_path: str,
    available_encoders: set[str] | None = None,
) -> ExportPlan:
    for clip in clips:
        clip.reset_full_range()
        if clip.sequence_missing_count:
            preview = "、".join(str(value) for value in clip.sequence_missing_preview[:20])
            raise RuntimeError(
                f"{clip.name} 检测到 {clip.sequence_missing_count} 个缺失编号"
                + (f"（例如 {preview}）" if preview else "")
                + "。请补齐序列后再导出。"
            )

    output = str(Path(output_path).resolve())
    extension = Path(output).suffix.lower().lstrip(".")
    codec = settings.sequence_codec
    if codec not in {"h264_lossless", "h265_lossless", "ffv1"}:
        raise RuntimeError(f"未知的序列帧编码模式：{codec}")
    if extension not in {"mp4", "mov", "mkv"}:
        raise RuntimeError("序列帧转视频仅支持 MP4、MOV 或 MKV 容器。")
    if codec == "ffv1" and extension == "mp4":
        raise RuntimeError("MP4 容器不支持 FFV1。请选择 MOV 或 MKV。")

    bitrate_mode = bool(settings.sequence_bitrate_enabled)
    bitrate_mbps = int(settings.sequence_bitrate_mbps)
    if bitrate_mode and codec == "ffv1":
        raise RuntimeError("FFV1 只提供数学无损输出，不支持目标码流模式。")
    if bitrate_mode and not 1 <= bitrate_mbps <= 1000:
        raise RuntimeError("目标码流必须在 1–1000 Mbps 之间。")

    first = clips[0]
    if codec in {"h264_lossless", "h265_lossless"} and first.has_alpha:
        raise RuntimeError(
            "H.264/H.265 无法可靠保留序列帧透明通道。请改用 FFV1，并选择 MOV 或 MKV。"
        )
    if codec == "h264_lossless" and first.bit_depth > 8:
        raise RuntimeError("H.264 RGB 真无损模式仅支持 8-bit 序列。高位深序列请使用 H.265 或 FFV1。")
    if codec == "h265_lossless" and first.bit_depth > 12:
        raise RuntimeError("H.265 真无损模式最高支持 12-bit。16-bit/浮点序列请使用 FFV1。")

    command = [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error", "-nostdin"]
    filters: list[str] = []
    labels: list[str] = []
    for index, clip in enumerate(clips):
        command += [
            "-thread_queue_size", "512",
            "-framerate", clip.fps_expression,
            "-start_number", str(clip.sequence_start_number),
            "-i", clip.sequence_pattern,
        ]
        filters.append(f"[{index}:v]setpts=PTS-STARTPTS[v{index}]")
        labels.append(f"[v{index}]")
    filters.append("".join(labels) + f"concat=n={len(clips)}:v=1:a=0[outv]")
    command += ["-filter_complex", ";".join(filters), "-map", "[outv]", "-an"]

    warnings: list[str]
    encoder_label: str
    if bitrate_mode:
        rate = f"{bitrate_mbps}M"
        buffer_size = f"{min(2000, bitrate_mbps * 2)}M"
        backend, hardware_encoder, backend_notes = resolve_sequence_backend(
            codec, settings.sequence_encoder_backend, available_encoders, first.bit_depth
        )
        common_warnings = [
            f"{'H.264' if codec == 'h264_lossless' else 'H.265'} 将按 {bitrate_mbps} Mbps 目标码流编码；该模式属于有损压缩，不再是逐像素无损。",
        ]
        if backend != "cpu" and hardware_encoder:
            hardware_args, hardware_label, hardware_warnings = _hardware_bitrate_args(
                backend, hardware_encoder, codec, first.bit_depth, rate, buffer_size
            )
            command += hardware_args
            if codec == "h265_lossless" and extension in {"mp4", "mov"}:
                command += ["-tag:v", "hvc1"]
            encoder_label = f"{hardware_encoder} {bitrate_mbps} Mbps"
            warnings = common_warnings + hardware_warnings + backend_notes
        elif codec == "h264_lossless":
            command += [
                "-c:v", "libx264", "-preset", "medium",
                "-b:v", rate, "-maxrate", rate, "-bufsize", buffer_size,
                "-pix_fmt", "yuv420p", "-profile:v", "high",
            ]
            encoder_label = f"libx264 {bitrate_mbps} Mbps"
            warnings = common_warnings + [
                "当前使用 CPU 软件编码。为提高 MP4/MOV 与常见播放器兼容性，码流模式使用 YUV 4:2:0。",
            ] + backend_notes
        else:
            if first.bit_depth <= 8:
                pixel_format = "yuv420p"
            elif first.bit_depth <= 10:
                pixel_format = "yuv420p10le"
            else:
                pixel_format = "yuv420p12le"
            command += [
                "-c:v", "libx265", "-preset", "medium",
                "-b:v", rate, "-maxrate", rate, "-bufsize", buffer_size,
                "-pix_fmt", pixel_format, "-x265-params", "log-level=error",
            ]
            if extension in {"mp4", "mov"}:
                command += ["-tag:v", "hvc1"]
            encoder_label = f"libx265 {bitrate_mbps} Mbps"
            warnings = common_warnings + [
                "当前使用 CPU 软件编码；H.265 在相同目标码流下通常比 H.264 保留更多细节，但编码速度更慢。",
            ] + backend_notes
    elif codec == "h264_lossless":
        command += [
            "-c:v", "libx264rgb", "-preset", "medium", "-crf", "0",
            "-pix_fmt", "rgb24",
        ]
        encoder_label = "libx264rgb lossless"
        warnings = [
            "H.264 采用 RGB 4:4:4 真无损编码，可保持 8-bit RGB 像素；文件通常较大。",
            "该无损 H.264 使用 High 4:4:4 Predictive，部分电视、手机硬件播放器可能不支持硬解。",
        ]
    elif codec == "h265_lossless":
        if first.bit_depth <= 8:
            pixel_format = "gbrp"
        elif first.bit_depth <= 10:
            pixel_format = "gbrp10le"
        else:
            pixel_format = "gbrp12le"
        command += [
            "-c:v", "libx265", "-preset", "medium",
            "-x265-params", "lossless=1:log-level=error",
            "-pix_fmt", pixel_format,
        ]
        if extension in {"mp4", "mov"}:
            command += ["-tag:v", "hvc1"]
        encoder_label = "libx265 lossless"
        warnings = [
            "H.265 采用 RGB 4:4:4 真无损编码，压缩率通常优于无损 H.264，但编码更慢。",
            "该无损 H.265 使用 Range Extensions，部分电视、手机硬件播放器可能不支持硬解。",
        ]
    else:
        command += [
            "-c:v", "ffv1", "-level", "3", "-coder", "1", "-context", "1",
            "-g", "1", "-slicecrc", "1",
        ]
        if first.pix_fmt:
            command += ["-pix_fmt", first.pix_fmt]
        encoder_label = "ffv1"
        warnings = [
            "FFV1 是面向归档和后期的数学无损编码，可保留高位深与透明通道，但普通播放器兼容性不如 H.264/H.265。",
        ]

    if settings.faststart and extension in {"mp4", "mov"}:
        command += ["-movflags", "+faststart"]
    command += [
        "-r", first.fps_expression,
        "-fps_mode", "cfr",
        "-progress", "pipe:1", "-nostats", output,
    ]
    total_duration = sum(clip.duration for clip in clips)
    estimated_bytes = int(total_duration * bitrate_mbps * 1_000_000 / 8) if bitrate_mode else 0
    return ExportPlan(
        commands=[command],
        encoder=encoder_label,
        total_duration=total_duration,
        estimated_bytes=estimated_bytes,
        warnings=warnings + [
            "为保证逐帧连接，所有序列必须保持相同分辨率、输入帧率、像素格式和透明通道状态。",
        ],
    )


def build_join_plan(
    clips: list[MediaClip],
    settings: JoinSettings,
    output_path: str,
    ffmpeg_path: str,
    available_encoders: set[str] | None = None,
) -> ExportPlan:
    report = stream_copy_report(clips)
    if not report.compatible:
        raise RuntimeError("无法拼接或转视频：\n" + "\n".join(report.differences[:20]))

    if clips and all(clip.media_type == "sequence" for clip in clips):
        return _build_sequence_join_plan(clips, settings, output_path, ffmpeg_path, available_encoders)

    for clip in clips:
        clip.reset_full_range()
    concat_file = build_ffconcat(clips, use_ranges=False)
    output = str(Path(output_path).resolve())
    command = [
        ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-map", "0", "-c", "copy",
        "-fflags", "+genpts", "-avoid_negative_ts", "make_zero",
    ]
    extension = Path(output).suffix.lower()
    if settings.faststart and extension in {".mp4", ".mov", ".m4v"}:
        command += ["-movflags", "+faststart"]
    command += ["-progress", "pipe:1", "-nostats", output]
    return ExportPlan(
        commands=[command],
        temporary_files=[concat_file],
        encoder="copy",
        total_duration=sum(clip.duration for clip in clips),
        estimated_bytes=sum(max(0, clip.file_size) for clip in clips),
        warnings=["极速视频模式不会解码或重新编码；少数文件即使参数检查一致，也可能因编码器私有数据差异被封装器拒绝。"],
    )
