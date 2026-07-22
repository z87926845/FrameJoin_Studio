from __future__ import annotations

import os
import unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication
    from framejoin.i18n import tr
    from framejoin.main_window import MainWindow
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 unavailable")
class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_bilingual_strings(self) -> None:
        self.assertIn("序列", tr("zh_CN", "add_sequence")); self.assertIn("Sequence", tr("en_US", "add_sequence"))

    def test_main_window_constructs_when_tools_exist(self) -> None:
        from framejoin.tools import Toolchain
        if not Toolchain.detect().ffmpeg or not Toolchain.detect().ffprobe: self.skipTest("FFmpeg unavailable")
        window=MainWindow(); self.assertEqual(window.language_combo.count(),2); self.assertGreaterEqual(window.settings_panel.codec_combo.count(),3); window.close()


if __name__ == "__main__": unittest.main()
