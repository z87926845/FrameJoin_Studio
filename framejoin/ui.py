from __future__ import annotations

import sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from .brand import application_icon, pixmap, verify_branding
from .main_window import MainWindow


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("FrameJoin Studio")
    app.setOrganizationName("FrameJoinStudio")
    try:
        verify_branding()
        app.setWindowIcon(application_icon())
        splash = QSplashScreen(pixmap("splash_screen.svg"), Qt.WindowType.WindowStaysOnTopHint)
        splash.show(); app.processEvents()
        window = MainWindow()
    except Exception as exc:
        QMessageBox.critical(None, "FrameJoin Studio", str(exc)); return 1
    QTimer.singleShot(900, lambda: (window.show(), splash.finish(window)))
    return app.exec()
