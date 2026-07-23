from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from framejoin.brand_data import ASSET_HASHES, asset_bytes, verify_branding
from framejoin.exporter import build_join_plan, resolve_sequence_backend, stream_copy_report
from framejoin.i18n import tr
from framejoin.models import JoinSettings, MediaClip
from framejoin.probe import probe_image_sequence, probe_media
from framejoin.tools import EncoderCapabilities, Toolchain, hidden_subprocess_kwargs
from framejoin.ui_helpers import ExportThread


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tools = Toolchain.detect()

    def test_branding_hashes(self) -> None:
        verify_branding()
        for name, expected in ASSET_HASHES.items():
            self.assertEqual(hashlib.sha256(asset_bytes(name)).hexdigest(), expected)

    def test_bilingual_strings_without_gui(self) -> None:
        self.assertIn("序列", tr("zh_CN", "add_sequence"))
        self.assertIn("Sequence", tr("en_US", "add_sequence"))
        self.assertIn("转码", tr("zh_CN", "video_transcode_enable"))
        self.assertIn("Continuous", tr("en_US", "sequence_to_frames"))

    def test_backend_resolution(self) -> None:
        backend, encoder, _ = resolve_sequence_backend(
            "h264_lossless", "auto", {"h264_nvenc"}, 8
        )
        self.assertEqual((backend, encoder), ("nvenc", "h264_nvenc"))
        backend, encoder, notes = resolve_sequence_backend(
            "h265_lossless", "auto", set(), 12
        )
        self.assertEqual((backend, encoder), ("cpu", None))
        self.assertTrue(notes)

    def test_encoder_capability_labels(self) -> None:
        caps = EncoderCapabilities({"h264_nvenc"}, {"h264_nvenc"})
        self.assertTrue(caps.backend_available("nvenc", "h264_lossless"))
        self.assertFalse(caps.backend_available("qsv", "h264_lossless"))

    def test_mixed_media_is_blocked(self) -> None:
        report = stream_copy_report(
            [
                MediaClip(path="a.mp4", media_type="video"),
                MediaClip(
                    path="a0001.png",
                    media_type="sequence",
                    sequence_pattern="a%04d.png",
                ),
            ]
        )
        self.assertFalse(report.compatible)

    @staticmethod
    def _sequence_clip(folder: Path, prefix: str, frame_count: int) -> MediaClip:
        for index in range(1, frame_count + 1):
            (folder / f"{prefix}{index:04d}.png").write_bytes(
                f"{prefix}:{index}".encode("ascii")
            )
        clip = MediaClip(
            path=str(folder / f"{prefix}0001.png"),
            media_type="sequence",
            width=1920,
            height=1080,
            pix_fmt="rgba",
            has_alpha=True,
            total_frames=frame_count,
            sequence_actual_files=frame_count,
            sequence_start_number=1,
            sequence_end_number=frame_count,
            sequence_digits=4,
            sequence_prefix=prefix,
            sequence_suffix=".png",
            sequence_pattern=str(folder / f"{prefix}%04d.png"),
        )
        clip.set_fps_value("24000/1001")
        clip.reset_full_range()
        return clip

    def test_sequence_frames_are_copied_in_list_order_with_continuous_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            first_dir = root / "first"
            second_dir = root / "second"
            first_dir.mkdir()
            second_dir.mkdir()
            clips = [
                self._sequence_clip(first_dir, "a_", 2),
                self._sequence_clip(second_dir, "b_", 3),
            ]
            output = root / "joined_frames"
            plan = build_join_plan(
                clips,
                JoinSettings(
                    sequence_output_mode="frames",
                    sequence_frame_prefix="shot_",
                    sequence_frame_start=10,
                    sequence_frame_digits=5,
                ),
                str(output),
                "ffmpeg-not-used",
            )
            self.assertFalse(plan.commands)
            self.assertEqual(
                [name for _source, name in plan.file_copies],
                [
                    "shot_00010.png",
                    "shot_00011.png",
                    "shot_00012.png",
                    "shot_00013.png",
                    "shot_00014.png",
                ],
            )
            worker = ExportThread(plan, str(output))
            worker._run_file_copies()
            self.assertEqual(
                [path.name for path in sorted(output.iterdir())],
                [name for _source, name in plan.file_copies],
            )
            self.assertEqual((output / "shot_00010.png").read_bytes(), b"a_:1")
            self.assertEqual((output / "shot_00012.png").read_bytes(), b"b_:1")

    def test_video_transcode_accepts_mismatched_video_parameters(self) -> None:
        clips = [
            MediaClip(
                path="first.mp4",
                media_type="video",
                codec="h264",
                width=1920,
                height=1080,
                pix_fmt="yuv420p",
                fps_num=25,
                duration=1.0,
            ),
            MediaClip(
                path="second.mov",
                media_type="video",
                codec="hevc",
                width=1280,
                height=720,
                pix_fmt="yuv420p10le",
                fps_num=30,
                duration=1.0,
            ),
        ]
        self.assertFalse(stream_copy_report(clips).compatible)
        plan = build_join_plan(
            clips,
            JoinSettings(
                container="mp4",
                video_transcode_enabled=True,
                video_codec="h264",
                video_bitrate_mbps=50,
                video_encoder_backend="cpu",
                video_audio_mode="none",
            ),
            "output.mp4",
            "ffmpeg",
            set(),
        )
        joined = " ".join(plan.command)
        self.assertIn("concat=n=2:v=1:a=0", joined)
        self.assertIn("libx264", plan.command)
        self.assertIn("50M", plan.command)

    def test_video_audio_copy_remains_guarded(self) -> None:
        clips = [
            MediaClip(path="a.mp4", media_type="video", codec="h264", width=1920, height=1080, duration=1.0),
            MediaClip(path="b.mp4", media_type="video", codec="hevc", width=1280, height=720, duration=1.0),
        ]
        with self.assertRaisesRegex(RuntimeError, "原音频复制"):
            build_join_plan(
                clips,
                JoinSettings(
                    container="mp4",
                    video_transcode_enabled=True,
                    video_audio_mode="copy",
                    video_encoder_backend="cpu",
                ),
                "out.mp4",
                "ffmpeg",
                set(),
            )

    @unittest.skipUnless(
        Toolchain.detect().ffmpeg and Toolchain.detect().ffprobe,
        "FFmpeg unavailable",
    )
    def test_real_sequence_and_video_paths(self) -> None:
        ffmpeg, ffprobe = self.tools.ffmpeg, self.tools.ffprobe
        assert ffmpeg and ffprobe
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            sequence_dir = root / "sequence"
            sequence_dir.mkdir()
            for index in range(1, 6):
                subprocess.run(
                    [
                        ffmpeg,
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        f"color=c=0x{index * 20:02x}4060:s=96x64:d=0.04",
                        "-frames:v",
                        "1",
                        str(sequence_dir / f"frame_{index:04d}.png"),
                    ],
                    check=True,
                    **hidden_subprocess_kwargs(),
                )
            clip = probe_image_sequence(
                str(sequence_dir / "frame_0001.png"), ffprobe, "24000/1001"
            )
            self.assertEqual(clip.total_frames, 5)
            self.assertEqual(clip.fps_expression, "24000/1001")
            for codec, extension in (
                ("h264_lossless", "mp4"),
                ("h265_lossless", "mkv"),
                ("ffv1", "mkv"),
            ):
                output = root / f"out_{codec}.{extension}"
                plan = build_join_plan(
                    [clip],
                    JoinSettings(container=extension, sequence_codec=codec),
                    str(output),
                    ffmpeg,
                    set(),
                )
                subprocess.run(plan.command, check=True, **hidden_subprocess_kwargs())
                self.assertEqual(probe_media(str(output), ffprobe).total_frames, 5)

            videos = []
            for name, color in (("first.mkv", "red"), ("second.mkv", "blue")):
                target = root / name
                subprocess.run(
                    [
                        ffmpeg,
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        f"color={color}:s=96x64:r=25:d=0.2",
                        "-c:v",
                        "ffv1",
                        str(target),
                    ],
                    check=True,
                    **hidden_subprocess_kwargs(),
                )
                videos.append(probe_media(str(target), ffprobe))
            joined = root / "joined.mkv"
            plan = build_join_plan(
                videos,
                JoinSettings(container="mkv"),
                str(joined),
                ffmpeg,
            )
            subprocess.run(plan.command, check=True, **hidden_subprocess_kwargs())
            self.assertGreater(probe_media(str(joined), ffprobe).total_frames, 0)

            transcoded = root / "transcoded.mp4"
            plan = build_join_plan(
                videos,
                JoinSettings(
                    container="mp4",
                    video_transcode_enabled=True,
                    video_codec="h264",
                    video_bitrate_mbps=5,
                    video_encoder_backend="cpu",
                    video_audio_mode="none",
                ),
                str(transcoded),
                ffmpeg,
                set(),
            )
            subprocess.run(plan.command, check=True, **hidden_subprocess_kwargs())
            self.assertGreater(probe_media(str(transcoded), ffprobe).total_frames, 0)


if __name__ == "__main__":
    unittest.main()
