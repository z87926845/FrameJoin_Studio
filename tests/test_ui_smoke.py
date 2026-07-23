from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SKIP_UI_SMOKE = os.environ.get("FRAMEJOIN_SKIP_UI_SMOKE") == "1"

try:
    from PySide6.QtWidgets import QApplication

    from framejoin.i18n import tr
    from framejoin.main_window import MainWindow
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

    def test_main_window_constructs_when_tools_exist(self) -> None:
        from framejoin.tools import Toolchain

        tools = Toolchain.detect()
        if not tools.ffmpeg or not tools.ffprobe:
            self.skipTest("FFmpeg unavailable")
        window = MainWindow()
        self.assertEqual(window.language_combo.count(), 2)
        self.assertGreaterEqual(window.settings_panel.codec_combo.count(), 3)
        self.assertEqual(window.preview.mode_combo.count(), 2)
        self.assertFalse(window.settings_panel.lossy_options.isHidden())
        self.assertFalse(window.settings_panel.lossy_options.isEnabled())
        window.close()


if __name__ == "__main__":
    unittest.main()
