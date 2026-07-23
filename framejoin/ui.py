from __future__ import annotations

import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

from .brand import application_icon, pixmap, verify_branding
from .main_window import MainWindow


def _scaled_splash(app: QApplication):
    source = pixmap("splash_screen.png")
    screen = app.primaryScreen()
    if screen is None:
        return source
    available = screen.availableGeometry().size()
    max_width = min(1440, max(640, int(available.width() * 0.82)))
    max_height = min(810, max(360, int(available.height() * 0.82)))
    return source.scaled(
        max_width,
        max_height,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("FrameJoin Studio")
    app.setOrganizationName("FrameJoinStudio")
    try:
        verify_branding()
        app.setWindowIcon(application_icon())
        splash = QSplashScreen(_scaled_splash(app), Qt.WindowType.WindowStaysOnTopHint)
        splash.show()
        app.processEvents()
        window = MainWindow()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(None, "FrameJoin Studio", str(exc))
        return 1
    QTimer.singleShot(900, lambda: (window.show(), splash.finish(window)))
    return app.exec()
