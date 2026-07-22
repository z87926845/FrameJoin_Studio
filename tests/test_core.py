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
                subprocess.run(
                    plan.command,
                    check=True,
                    **hidden_subprocess_kwargs(),
                )
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


if __name__ == "__main__":
    unittest.main()
