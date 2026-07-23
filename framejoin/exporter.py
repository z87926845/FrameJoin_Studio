from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

from .models import JoinSettings, MediaClip, parse_fraction
from .preview import build_ffconcat


@dataclass(slots=True)
class ExportPlan:
    commands: list[list[str]] = field(default_factory=list)
    temporary_files: list[Path] = field(default_factory=list)
    encoder: str = ""
    total_duration: float = 0.0
    warnings: list[str] = field(default_factory=list)
    estimated_bytes: int = 0
    file_copies: list[tuple[Path, str]] = field(default_factory=list)
    output_directory: Path | None = None

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
            ["视频与序列帧不能在同一个任务中混拼。请分别导出。"],
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
            ("图像扩展名", lambda c: Path(c.sequence_file_for_frame(0)).suffix.lower()),
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
            return CompatibilityReport(False, differences, f"发现 {len(differences)} 项不一致")
        return CompatibilityReport(
            True,
            [],
            "序列参数一致，可按列表顺序复制为连续编号序列，或转为无损/目标码流视频",
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
        if settings.sequence_output_mode == "frames":
            return ""
        if settings.container in {"mp4", "mov", "mkv"}:
            return settings.container
        return "mp4" if settings.sequence_codec in {"h264_lossless", "h265_lossless"} else "mkv"
    if settings.video_transcode_enabled:
        return settings.container if settings.container in {"mp4", "mov", "mkv"} else "mp4"
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
    available = available_encoders or set()
    requested = requested if requested in {"auto", "cpu", "nvenc", "qsv", "amf", "videotoolbox"} else "auto"
    notes: list[str] = []
    hardware_allowed = not (codec == "h265_lossless" and bit_depth > 10)
    if requested == "cpu":
        return "cpu", None, notes
    if requested != "auto":
        name = _HARDWARE_ENCODERS[requested][codec]
        if not hardware_allowed:
            raise RuntimeError("当前素材超过 10-bit，所选显卡编码路径不能保证正确输出；请改用 CPU 软件编码。")
        if name not in available:
            raise RuntimeError(f"当前 FFmpeg 未提供 {_BACKEND_LABELS[requested]} 编码器（{name}）。")
        return requested, name, notes

    if hardware_allowed:
        backend_order = (
            ("videotoolbox", "nvenc", "qsv", "amf")
            if sys.platform == "darwin"
            else ("nvenc", "qsv", "amf", "videotoolbox")
        )
        for backend in backend_order:
            name = _HARDWARE_ENCODERS[backend][codec]
            if name in available:
                return backend, name, notes
    if bit_depth > 10 and codec == "h265_lossless":
        notes.append("当前素材超过 10-bit，自动模式已回退到 CPU 软件编码。")
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
        f"当前使用 {label} 进行硬件编码。",
        "硬件编码速度通常更快，但在相同码流下画质可能与 CPU 软件编码略有差异。",
    ]
    return args, label, warnings


def _bitrate_encoder_args(
    codec_key: str,
    requested_backend: str,
    available_encoders: set[str] | None,
    bit_depth: int,
    bitrate_mbps: int,
) -> tuple[list[str], str, list[str]]:
    rate = f"{bitrate_mbps}M"
    buffer_size = f"{min(2000, bitrate_mbps * 2)}M"
    backend, hardware_encoder, notes = resolve_sequence_backend(
        codec_key, requested_backend, available_encoders, bit_depth
    )
    if backend != "cpu" and hardware_encoder:
        args, label, warnings = _hardware_bitrate_args(
            backend, hardware_encoder, codec_key, bit_depth, rate, buffer_size
        )
        return args, f"{label} {bitrate_mbps} Mbps", warnings + notes
    if codec_key == "h264_lossless":
        return (
            [
                "-c:v", "libx264", "-preset", "medium",
                "-b:v", rate, "-maxrate", rate, "-bufsize", buffer_size,
                "-pix_fmt", "yuv420p", "-profile:v", "high",
            ],
            f"libx264 {bitrate_mbps} Mbps",
            ["当前使用 CPU 软件编码；为提高常见播放器兼容性，使用 YUV 4:2:0。"] + notes,
        )
    pixel_format = "yuv420p" if bit_depth <= 8 else "yuv420p10le"
    return (
        [
            "-c:v", "libx265", "-preset", "medium",
            "-b:v", rate, "-maxrate", rate, "-bufsize", buffer_size,
            "-pix_fmt", pixel_format, "-x265-params", "log-level=error",
        ],
        f"libx265 {bitrate_mbps} Mbps",
        ["当前使用 CPU H.265 软件编码。"] + notes,
    )


def _validate_sequences(clips: list[MediaClip]) -> None:
    for clip in clips:
        clip.reset_full_range()
        if clip.sequence_missing_count:
            preview = "、".join(str(value) for value in clip.sequence_missing_preview[:20])
            raise RuntimeError(
                f"{clip.name} 检测到 {clip.sequence_missing_count} 个缺失编号"
                + (f"（例如 {preview}）" if preview else "")
                + "。请补齐序列后再输出。"
            )


def _build_sequence_copy_plan(
    clips: list[MediaClip], settings: JoinSettings, output_path: str
) -> ExportPlan:
    _validate_sequences(clips)
    report = stream_copy_report(clips)
    if not report.compatible:
        raise RuntimeError("连续序列帧输出要求各段格式一致：\n" + "\n".join(report.differences[:20]))

    target = Path(output_path).expanduser().resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise RuntimeError("连续序列帧输出目录必须不存在或为空目录。")
    for clip in clips:
        source_dir = Path(clip.path).resolve().parent
        try:
            target.relative_to(source_dir)
        except ValueError:
            pass
        else:
            raise RuntimeError("输出目录不能位于任一源序列目录内部，以免覆盖或混入原始帧。")

    prefix = settings.sequence_frame_prefix.strip()
    if not prefix or any(value in prefix for value in ("/", "\\")) or prefix in {".", ".."}:
        raise RuntimeError("连续序列帧文件名前缀不能为空，也不能包含路径分隔符。")
    start = int(settings.sequence_frame_start)
    digits = int(settings.sequence_frame_digits)
    if start < 0:
        raise RuntimeError("连续序列帧起始编号不能小于 0。")
    if not 1 <= digits <= 12:
        raise RuntimeError("连续序列帧编号位数必须在 1–12 之间。")

    suffix = Path(clips[0].sequence_file_for_frame(0)).suffix
    jobs: list[tuple[Path, str]] = []
    estimated = 0
    number = start
    for clip in clips:
        for frame in range(clip.total_frames):
            source = Path(clip.sequence_file_for_frame(frame)).resolve()
            if not source.is_file():
                raise RuntimeError(f"找不到源序列帧：{source}")
            jobs.append((source, f"{prefix}{number:0{digits}d}{suffix}"))
            try:
                estimated += source.stat().st_size
            except OSError:
                pass
            number += 1

    return ExportPlan(
        encoder="byte-for-byte image copy",
        total_duration=sum(clip.duration for clip in clips),
        estimated_bytes=estimated,
        file_copies=jobs,
        output_directory=target,
        warnings=[
            "连续序列帧模式不会修改原始文件，也不会重新编码图像；软件会复制原始字节并重新连续编号。",
            "全部帧先写入同级临时目录，成功后再一次性切换为最终输出目录。",
        ],
    )


def _build_sequence_join_plan(
    clips: list[MediaClip],
    settings: JoinSettings,
    output_path: str,
    ffmpeg_path: str,
    available_encoders: set[str] | None = None,
) -> ExportPlan:
    _validate_sequences(clips)
    report = stream_copy_report(clips)
    if not report.compatible:
        raise RuntimeError("序列帧参数不一致：\n" + "\n".join(report.differences[:20]))

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
        raise RuntimeError("H.264/H.265 无法可靠保留透明通道。请改用 FFV1，并选择 MOV 或 MKV。")
    if codec == "h264_lossless" and first.bit_depth > 8:
        raise RuntimeError("H.264 RGB 真无损模式仅支持 8-bit 序列。")
    if codec == "h265_lossless" and first.bit_depth > 12:
        raise RuntimeError("H.265 真无损模式最高支持 12-bit。16-bit/浮点序列请使用 FFV1。")

    command = [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error", "-nostdin"]
    filters: list[str] = []
    labels: list[str] = []
    for index, clip in enumerate(clips):
        command += [
            "-thread_queue_size", "512", "-framerate", clip.fps_expression,
            "-start_number", str(clip.sequence_start_number), "-i", clip.sequence_pattern,
        ]
        filters.append(f"[{index}:v]setpts=PTS-STARTPTS[v{index}]")
        labels.append(f"[v{index}]")
    filters.append("".join(labels) + f"concat=n={len(clips)}:v=1:a=0[outv]")
    command += ["-filter_complex", ";".join(filters), "-map", "[outv]", "-an"]

    if bitrate_mode:
        encoder_args, encoder_label, warnings = _bitrate_encoder_args(
            codec,
            settings.sequence_encoder_backend,
            available_encoders,
            first.bit_depth,
            bitrate_mbps,
        )
        command += encoder_args
        warnings.insert(0, f"当前按 {bitrate_mbps} Mbps 输出，属于有损压缩。")
    elif codec == "h264_lossless":
        command += ["-c:v", "libx264rgb", "-preset", "medium", "-crf", "0", "-pix_fmt", "rgb24"]
        encoder_label = "libx264rgb lossless"
        warnings = ["H.264 RGB 4:4:4 真无损文件较大，部分硬件播放器不支持。"]
    elif codec == "h265_lossless":
        pixel_format = "gbrp" if first.bit_depth <= 8 else ("gbrp10le" if first.bit_depth <= 10 else "gbrp12le")
        command += [
            "-c:v", "libx265", "-preset", "medium",
            "-x265-params", "lossless=1:log-level=error", "-pix_fmt", pixel_format,
        ]
        encoder_label = "libx265 lossless"
        warnings = ["H.265 RGB 4:4:4 真无损压缩率较高，但编码更慢且部分硬件播放器不支持。"]
    else:
        command += ["-c:v", "ffv1", "-level", "3", "-coder", "1", "-context", "1", "-g", "1", "-slicecrc", "1"]
        if first.pix_fmt:
            command += ["-pix_fmt", first.pix_fmt]
        encoder_label = "ffv1"
        warnings = ["FFV1 适合归档和后期，可保留高位深与透明通道。"]

    if codec == "h265_lossless" and extension in {"mp4", "mov"}:
        command += ["-tag:v", "hvc1"]
    if settings.faststart and extension in {"mp4", "mov"}:
        command += ["-movflags", "+faststart"]
    command += ["-r", first.fps_expression, "-fps_mode", "cfr", "-progress", "pipe:1", "-nostats", output]
    total_duration = sum(clip.duration for clip in clips)
    estimated_bytes = int(total_duration * bitrate_mbps * 1_000_000 / 8) if bitrate_mode else 0
    return ExportPlan(
        commands=[command],
        encoder=encoder_label,
        total_duration=total_duration,
        estimated_bytes=estimated_bytes,
        warnings=warnings,
    )


def _target_video_fps(clips: list[MediaClip], settings: JoinSettings) -> str:
    if settings.video_fps_mode == "custom":
        fraction = parse_fraction(settings.video_fps)
        if fraction <= 0:
            raise RuntimeError("视频自定义输出帧率必须大于 0。")
        fraction = fraction.limit_denominator(100_000)
        return str(fraction.numerator) if fraction.denominator == 1 else f"{fraction.numerator}/{fraction.denominator}"
    expression = clips[0].fps_expression
    return expression if expression != "0" else "24"


def _video_normalize_filter(index: int, width: int, height: int, fps: str) -> str:
    return (
        f"[{index}:v:0]setpts=PTS-STARTPTS,"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}[v{index}]"
    )


def _build_video_transcode_plan(
    clips: list[MediaClip],
    settings: JoinSettings,
    output_path: str,
    ffmpeg_path: str,
    available_encoders: set[str] | None,
) -> ExportPlan:
    output = str(Path(output_path).resolve())
    extension = Path(output).suffix.lower().lstrip(".")
    if extension not in {"mp4", "mov", "mkv"}:
        raise RuntimeError("视频转码拼接仅支持 MP4、MOV 或 MKV。")
    if settings.video_codec not in {"h264", "h265"}:
        raise RuntimeError("视频转码编码格式必须是 H.264 或 H.265。")
    bitrate_mbps = int(settings.video_bitrate_mbps)
    if not 1 <= bitrate_mbps <= 1000:
        raise RuntimeError("视频目标码流必须在 1–1000 Mbps 之间。")

    first = clips[0]
    width = max(2, int(first.width) - int(first.width) % 2)
    height = max(2, int(first.height) - int(first.height) % 2)
    fps = _target_video_fps(clips, settings)
    codec_key = "h264_lossless" if settings.video_codec == "h264" else "h265_lossless"
    bit_depth = 10 if settings.video_codec == "h265" and any(clip.bit_depth > 8 for clip in clips) else 8
    encoder_args, encoder_label, encoder_warnings = _bitrate_encoder_args(
        codec_key,
        settings.video_encoder_backend,
        available_encoders,
        bit_depth,
        bitrate_mbps,
    )

    temporary_files: list[Path] = []
    audio_mode = settings.video_audio_mode if settings.video_audio_mode in {"aac", "copy", "none"} else "aac"
    if audio_mode == "copy":
        report = stream_copy_report(clips)
        if not report.compatible or not all(clip.has_audio for clip in clips):
            raise RuntimeError(
                "原音频复制只适用于所有视频流参数及音频参数一致的素材。"
                "参数不同的视频请选择 AAC 音频重编码或无音频。"
            )
        concat_file = build_ffconcat(clips, use_ranges=False)
        temporary_files.append(concat_file)
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}"
        )
        command = [
            ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-map", "0:v:0", "-map", "0:a:0", "-vf", vf,
        ]
        command += encoder_args + ["-c:a", "copy"]
    else:
        command = [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error", "-nostdin"]
        filters: list[str] = []
        for index, clip in enumerate(clips):
            command += ["-thread_queue_size", "512", "-i", str(Path(clip.path).resolve())]
            filters.append(_video_normalize_filter(index, width, height, fps))
            if audio_mode == "aac":
                duration = max(0.001, float(clip.duration))
                if clip.has_audio:
                    filters.append(
                        f"[{index}:a:0]aresample=48000,"
                        "aformat=sample_fmts=fltp:channel_layouts=stereo,"
                        f"atrim=duration={duration:.9f},asetpts=PTS-STARTPTS[a{index}]"
                    )
                else:
                    filters.append(
                        f"anullsrc=r=48000:cl=stereo,atrim=duration={duration:.9f},"
                        f"asetpts=PTS-STARTPTS[a{index}]"
                    )
        if audio_mode == "aac":
            concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(clips)))
            filters.append(f"{concat_inputs}concat=n={len(clips)}:v=1:a=1[outv][outa]")
            command += ["-filter_complex", ";".join(filters), "-map", "[outv]", "-map", "[outa]"]
            command += encoder_args + ["-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2"]
        else:
            concat_inputs = "".join(f"[v{i}]" for i in range(len(clips)))
            filters.append(f"{concat_inputs}concat=n={len(clips)}:v=1:a=0[outv]")
            command += ["-filter_complex", ";".join(filters), "-map", "[outv]", "-an"]
            command += encoder_args

    if settings.video_codec == "h265" and extension in {"mp4", "mov"}:
        command += ["-tag:v", "hvc1"]
    if settings.faststart and extension in {"mp4", "mov"}:
        command += ["-movflags", "+faststart"]
    command += ["-progress", "pipe:1", "-nostats", output]

    total_duration = sum(max(0.0, clip.duration) for clip in clips)
    audio_rate = 320_000 if audio_mode == "aac" else 0
    estimated = int(total_duration * ((bitrate_mbps * 1_000_000) + audio_rate) / 8)
    warnings = [
        "视频转码拼接会重新编码画面，不再是原码无损拼接。",
        f"所有片段会统一为第1段分辨率 {width}×{height} 和 {fps} fps。",
    ] + encoder_warnings
    if audio_mode == "copy":
        warnings.append("音频保持原始码流；仅在所有素材流参数一致时可用。")
    elif audio_mode == "aac":
        warnings.append("音频统一转为 AAC 320 kbps、48 kHz、立体声；无音频片段会补等长静音。")
    else:
        warnings.append("输出文件不包含音频。")
    return ExportPlan(
        commands=[command],
        temporary_files=temporary_files,
        encoder=encoder_label,
        total_duration=total_duration,
        estimated_bytes=estimated,
        warnings=warnings,
    )


def _build_video_stream_copy_plan(
    clips: list[MediaClip], settings: JoinSettings, output_path: str, ffmpeg_path: str
) -> ExportPlan:
    report = stream_copy_report(clips)
    if not report.compatible:
        raise RuntimeError("无法直接原码拼接：\n" + "\n".join(report.differences[:20]))
    for clip in clips:
        clip.reset_full_range()
    concat_file = build_ffconcat(clips, use_ranges=False)
    output = str(Path(output_path).resolve())
    command = [
        ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-map", "0", "-c", "copy", "-fflags", "+genpts", "-avoid_negative_ts", "make_zero",
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
        warnings=["极速视频模式不会解码或重新编码。"],
    )


def build_join_plan(
    clips: list[MediaClip],
    settings: JoinSettings,
    output_path: str,
    ffmpeg_path: str,
    available_encoders: set[str] | None = None,
) -> ExportPlan:
    if not clips:
        raise RuntimeError("没有素材。")
    media_types = {clip.media_type for clip in clips}
    if len(media_types) != 1:
        raise RuntimeError("视频与序列帧不能在同一个任务中混合输出。")
    if media_types == {"sequence"}:
        if settings.sequence_output_mode == "frames":
            return _build_sequence_copy_plan(clips, settings, output_path)
        return _build_sequence_join_plan(clips, settings, output_path, ffmpeg_path, available_encoders)
    if settings.video_transcode_enabled:
        return _build_video_transcode_plan(clips, settings, output_path, ffmpeg_path, available_encoders)
    return _build_video_stream_copy_plan(clips, settings, output_path, ffmpeg_path)
