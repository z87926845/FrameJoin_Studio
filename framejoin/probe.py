from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .models import MediaClip, parse_fraction
from .tools import CREATE_NO_WINDOW


VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".mxf", ".mts", ".m2ts", ".ts",
    ".webm", ".flv", ".wmv", ".vob", ".mpg", ".mpeg", ".m4v", ".3gp",
    ".ogv", ".divx", ".dav", ".264", ".h264", ".265", ".h265", ".266", ".vvc",
}


def is_video_path(path: str) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _stream_signature(streams: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for stream in streams:
        kind = str(stream.get("codec_type") or "unknown")
        codec = str(stream.get("codec_name") or "unknown")
        result.append(f"{kind}:{codec}")
    return result


def probe_media(path: str, ffprobe_path: str) -> MediaClip:
    command = [
        ffprobe_path, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe 无法读取该文件")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe 返回了无效 JSON") from exc

    streams = payload.get("streams", [])
    format_info = payload.get("format", {})
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video:
        raise RuntimeError("文件中没有视频流")
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)

    avg = parse_fraction(video.get("avg_frame_rate"))
    nominal = parse_fraction(video.get("r_frame_rate"))
    fps_fraction = avg if avg > 0 else nominal
    fps = float(fps_fraction) if fps_fraction > 0 else 0.0
    duration = _float(video.get("duration"), _float(format_info.get("duration")))
    total_frames = _int(video.get("nb_frames"))
    if total_frames <= 0 and duration > 0 and fps > 0:
        total_frames = max(1, round(duration * fps))
    if duration <= 0 and total_frames > 0 and fps > 0:
        duration = total_frames / fps

    avg_float = float(avg) if avg > 0 else 0.0
    nominal_float = float(nominal) if nominal > 0 else 0.0
    is_vfr = bool(avg_float and nominal_float and abs(avg_float - nominal_float) > 0.01)

    coded_width = _int(video.get("width"))
    coded_height = _int(video.get("height"))
    rotation = _int((video.get("tags") or {}).get("rotate"))
    for side_data in video.get("side_data_list") or []:
        if side_data.get("rotation") is not None:
            rotation = _int(side_data.get("rotation"))
            break
    if rotation % 360 in {90, 270}:
        display_width, display_height = coded_height, coded_width
    else:
        display_width, display_height = coded_width, coded_height

    timecode = str((video.get("tags") or {}).get("timecode") or (format_info.get("tags") or {}).get("timecode") or "")
    if not timecode:
        for stream in streams:
            tags = stream.get("tags") or {}
            if tags.get("timecode"):
                timecode = str(tags.get("timecode"))
                break

    time_base = parse_fraction(video.get("time_base"))
    source_path = Path(path).resolve()
    file_size = _int(format_info.get("size"))
    if file_size <= 0:
        try:
            file_size = source_path.stat().st_size
        except OSError:
            file_size = 0

    clip = MediaClip(
        path=str(source_path),
        codec=str(video.get("codec_name") or "unknown"),
        codec_long_name=str(video.get("codec_long_name") or ""),
        codec_tag=str(video.get("codec_tag_string") or ""),
        profile=str(video.get("profile") or ""),
        level=_int(video.get("level")),
        width=display_width,
        height=display_height,
        coded_width=coded_width,
        coded_height=coded_height,
        rotation=rotation,
        pix_fmt=str(video.get("pix_fmt") or ""),
        field_order=str(video.get("field_order") or ""),
        color_range=str(video.get("color_range") or ""),
        color_space=str(video.get("color_space") or ""),
        color_transfer=str(video.get("color_transfer") or ""),
        color_primaries=str(video.get("color_primaries") or ""),
        chroma_location=str(video.get("chroma_location") or ""),
        fps_num=fps_fraction.numerator if fps_fraction > 0 else 0,
        fps_den=fps_fraction.denominator if fps_fraction > 0 else 1,
        source_r_fps=nominal_float,
        source_avg_fps=avg_float,
        time_base_num=time_base.numerator if time_base > 0 else 0,
        time_base_den=time_base.denominator if time_base > 0 else 1,
        duration=duration,
        total_frames=total_frames,
        is_vfr=is_vfr,
        bit_rate=_int(video.get("bit_rate"), _int(format_info.get("bit_rate"))),
        file_size=file_size,
        format_name=str(format_info.get("format_name") or ""),
        source_timecode=timecode,
        stream_signature=_stream_signature(streams),
        has_audio=audio is not None,
        audio_codec=str(audio.get("codec_name") or "") if audio else "",
        audio_profile=str(audio.get("profile") or "") if audio else "",
        audio_sample_rate=_int(audio.get("sample_rate")) if audio else 0,
        audio_channels=_int(audio.get("channels")) if audio else 0,
        audio_sample_fmt=str(audio.get("sample_fmt") or "") if audio else "",
        audio_channel_layout=str(audio.get("channel_layout") or "") if audio else "",
        start_frame=0,
        end_frame=total_frames,
    )
    clip.normalize_range()
    return clip

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".tga", ".bmp", ".dpx", ".exr", ".webp", ".jxl",
}


def is_image_path(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def _probe_still(path: str, ffprobe_path: str) -> dict[str, Any]:
    command = [
        ffprobe_path, "-v", "error", "-print_format", "json",
        "-show_streams", "-select_streams", "v:0", path,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe 无法读取序列帧")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe 返回了无效 JSON") from exc
    stream = next((item for item in payload.get("streams", []) if item.get("codec_type") == "video"), None)
    if not stream:
        raise RuntimeError("所选文件不是可读取的图像")
    return stream


def probe_image_sequence(path: str, ffprobe_path: str, fps: str | float = 24.0) -> MediaClip:
    import re

    selected = Path(path).resolve()
    if not selected.is_file():
        raise RuntimeError("序列帧文件不存在")
    if selected.suffix.lower() not in IMAGE_EXTENSIONS:
        raise RuntimeError("不支持的序列帧格式")

    match = re.match(r"^(.*?)(\d+)(\.[^.]+)$", selected.name)
    if not match:
        raise RuntimeError("文件名末尾没有连续数字，无法识别为序列帧")
    prefix, number_text, suffix = match.groups()
    digits = len(number_text)
    matcher = re.compile(rf"^{re.escape(prefix)}(\d{{{digits}}}){re.escape(suffix)}$", re.IGNORECASE)

    numbered: dict[int, Path] = {}
    total_size = 0
    for item in selected.parent.iterdir():
        if not item.is_file():
            continue
        item_match = matcher.match(item.name)
        if not item_match:
            continue
        number = int(item_match.group(1))
        numbered[number] = item
        try:
            total_size += item.stat().st_size
        except OSError:
            pass
    if not numbered:
        raise RuntimeError("没有找到同名编号序列")

    start_number = min(numbered)
    end_number = max(numbered)
    expected_numbers = range(start_number, end_number + 1)
    missing = [number for number in expected_numbers if number not in numbered]
    total_frames = end_number - start_number + 1

    stream = _probe_still(str(numbered[start_number]), ffprobe_path)
    width = _int(stream.get("width"))
    height = _int(stream.get("height"))
    pix_fmt = str(stream.get("pix_fmt") or "")
    alpha_tokens = ("rgba", "bgra", "argb", "abgr", "yuva", "gbrap", "ya8", "ya16")
    has_alpha = any(token in pix_fmt.lower() for token in alpha_tokens)

    pattern = str(selected.parent / f"{prefix}%0{digits}d{suffix}")
    clip = MediaClip(
        path=str(numbered[start_number]),
        media_type="sequence",
        codec=selected.suffix.lower().lstrip("."),
        codec_long_name="Image sequence",
        width=width,
        height=height,
        coded_width=width,
        coded_height=height,
        pix_fmt=pix_fmt,
        field_order="progressive",
        color_range=str(stream.get("color_range") or ""),
        color_space=str(stream.get("color_space") or ""),
        color_transfer=str(stream.get("color_transfer") or ""),
        color_primaries=str(stream.get("color_primaries") or ""),
        chroma_location=str(stream.get("chroma_location") or ""),
        duration=0.0,
        total_frames=total_frames,
        is_vfr=False,
        file_size=total_size,
        format_name="image2",
        stream_signature=[f"video:{selected.suffix.lower().lstrip('.')}"],
        has_audio=False,
        start_frame=0,
        end_frame=total_frames,
        sequence_pattern=pattern,
        sequence_start_number=start_number,
        sequence_end_number=end_number,
        sequence_digits=digits,
        sequence_prefix=prefix,
        sequence_suffix=suffix,
        sequence_missing_count=len(missing),
        sequence_missing_preview=missing[:100],
        sequence_actual_files=len(numbered),
        has_alpha=has_alpha,
    )
    clip.set_fps_value(fps)
    clip.normalize_range()
    return clip
