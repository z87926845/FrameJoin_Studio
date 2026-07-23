from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SKIP_UI_SMOKE = os.environ.get("FRAMEJOIN_SKIP_UI_SMOKE") == "1"

try:
    from PySide6.QtWidgets import QApplication

    from framejoin.i18n import tr
    from framejoin.main_window import MainWindow
    from framejoin.models import MediaClip
    from framejoin.preview_widget import PreviewWidget
    from framejoin.tools import Toolchain
except ImportError:
    QApplication = None


@unittest.skipIf(
    QApplication is None or SKIP_UI_SMOKE,
    "PySide6 unavailable or GUI smoke test disabled on this runner",
)
class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_bilingual_strings(self) -> None:
        self.assertIn("序列", tr("zh_CN", "add_sequence"))
        self.assertIn("Sequence", tr("en_US", "add_sequence"))
        self.assertIn("实际帧率", tr("zh_CN", "preview_sequence_clock"))
        self.assertIn("hardware", tr("en_US", "preview_video_hw").lower())
        self.assertIn("转码", tr("zh_CN", "video_transcode_enable"))

    def test_main_window_constructs_when_tools_exist(self) -> None:
        tools = Toolchain.detect()
        if not tools.ffmpeg or not tools.ffprobe:
            self.skipTest("FFmpeg unavailable")
        window = MainWindow()
        panel = window.settings_panel
        self.assertEqual(window.language_combo.count(), 2)
        self.assertGreaterEqual(panel.codec_combo.count(), 3)
        self.assertEqual(panel.sequence_mode_combo.count(), 2)
        self.assertEqual(window.preview.mode_combo.count(), 2)
        self.assertFalse(panel.lossy_options.isHidden())
        self.assertFalse(panel.lossy_options.isEnabled())

        panel.sequence_mode_combo.setCurrentIndex(panel.sequence_mode_combo.findData("frames"))
        self.assertFalse(panel.frame_card.isHidden())
        self.assertTrue(panel.lossy_card.isHidden())
        self.assertTrue(panel.output_is_directory())

        panel.set_video_mode(True)
        self.assertFalse(panel.video_card.isHidden())
        self.assertFalse(panel.video_options.isEnabled())
        panel.video_transcode_check.setChecked(True)
        self.assertTrue(panel.video_options.isEnabled())
        self.assertFalse(panel.output_is_directory())
        window.close()

    def test_three_sequence_segments_use_one_continuous_timeline(self) -> None:
        preview = PreviewWidget(Toolchain(ffmpeg=None, ffprobe=None))
        clips = []
        for index in range(3):
            clip = MediaClip(
                path=f"segment_{index}/frame_0001.png",
                media_type="sequence",
                total_frames=25,
                sequence_start_number=1,
                sequence_digits=4,
                sequence_prefix="frame_",
                sequence_suffix=".png",
                sequence_pattern=f"segment_{index}/frame_%04d.png",
            )
            clip.set_fps_value("25")
            clips.append(clip)
        preview.set_clips(clips)
        self.assertEqual(preview.slider.maximum(), 3000)
        self.assertEqual(preview._locate(999)[0], 0)
        self.assertEqual(preview._locate(1000)[0], 1)
        self.assertEqual(preview._locate(1999)[0], 1)
        self.assertEqual(preview._locate(2000)[0], 2)
        preview.close()


if __name__ == "__main__":
    unittest.main()
