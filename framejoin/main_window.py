from __future__ import annotations

import os
import sys

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .brand import application_icon
from .i18n import LANGUAGES, tr
from .main_actions import MainActionsMixin
from .preview_widget import PreviewWidget
from .tools import EncoderCapabilities, Toolchain
from .ui_helpers import DropListWidget
from .ui_settings import SettingsPanel


class MainWindow(MainActionsMixin, QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings_store = QSettings("FrameJoinStudio", "FrameJoinStudio")
        self.language = self.settings_store.value("language", "zh_CN")
        if self.language not in LANGUAGES:
            self.language = "zh_CN"
        self.tools = Toolchain.detect()
        if not self.tools.ffmpeg or not self.tools.ffprobe:
            raise RuntimeError("FFmpeg/ffprobe not found. 请将它们放入 tools/ 或系统 PATH。")
        self.capabilities = EncoderCapabilities.detect(self.tools.ffmpeg)
        self.export_thread = None
        self._cpu_fallback_attempted = False
        self.setWindowIcon(application_icon())
        self.resize(1380, 860)
        self.setMinimumSize(1040, 680)
        self._build_ui()
        self.retranslate()
        self.refresh_mode()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 16)
        root.setSpacing(10)

        header = QHBoxLayout()
        self.heading = QLabel("FrameJoin Studio")
        self.heading.setObjectName("appHeading")
        self.subheading = QLabel()
        self.subheading.setObjectName("appSubheading")
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_box.addWidget(self.heading)
        title_box.addWidget(self.subheading)
        header.addLayout(title_box)
        header.addStretch(1)
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(118)
        for code, label in LANGUAGES.items():
            self.language_combo.addItem(label, code)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.language)))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language_label)
        header.addWidget(self.language_combo)
        root.addLayout(header)

        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("toolbarFrame")
        toolbar = QHBoxLayout(toolbar_frame)
        toolbar.setContentsMargins(10, 8, 10, 8)
        toolbar.setSpacing(7)
        self.add_video_button = QPushButton()
        self.add_sequence_button = QPushButton()
        self.remove_button = QPushButton()
        self.clear_button = QPushButton()
        self.up_button = QPushButton()
        self.down_button = QPushButton()
        self.save_button = QPushButton()
        self.load_button = QPushButton()
        for button in (
            self.add_video_button,
            self.add_sequence_button,
            self.remove_button,
            self.clear_button,
            self.up_button,
            self.down_button,
            self.save_button,
            self.load_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        root.addWidget(toolbar_frame)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        self.media_group = QGroupBox()
        media_layout = QVBoxLayout(self.media_group)
        self.media_list = DropListWidget()
        self.media_list.paths_dropped.connect(self.add_paths)
        self.media_list.currentItemChanged.connect(self._selection_changed)
        model = self.media_list.model()
        model.rowsInserted.connect(lambda *_args: self._sync_preview(False))
        model.rowsRemoved.connect(lambda *_args: self._sync_preview(False))
        model.rowsMoved.connect(lambda *_args: self._sync_preview(False))
        media_layout.addWidget(self.media_list)
        left_layout.addWidget(self.media_group, 2)

        self.preview_group = QGroupBox()
        preview_layout = QVBoxLayout(self.preview_group)
        self.preview = PreviewWidget(self.tools, self.language)
        self.preview.message.connect(self._preview_message)
        preview_layout.addWidget(self.preview)
        left_layout.addWidget(self.preview_group, 3)
        splitter.addWidget(left)

        self.settings_panel = SettingsPanel(self.capabilities, self.language)
        self.settings_panel.setMinimumWidth(410)
        splitter.addWidget(self.settings_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setMaximumWidth(380)
        footer.addWidget(self.status_label, 1)
        footer.addWidget(self.progress)
        root.addLayout(footer)

        self.add_video_button.clicked.connect(self.add_video_dialog)
        self.add_sequence_button.clicked.connect(self.add_sequence_dialog)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self._clear)
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        self.save_button.clicked.connect(self.save_project)
        self.load_button.clicked.connect(self.load_project)
        self.settings_panel.browse_requested.connect(self.browse_output)
        self.settings_panel.start_requested.connect(self.start_export)
        self.settings_panel.cancel_requested.connect(self.cancel_export)
        self.settings_panel.fps_apply_requested.connect(self.apply_fps)
        self.settings_panel.container_combo.currentIndexChanged.connect(self.refresh_mode)
        self.settings_panel.codec_combo.currentIndexChanged.connect(self.refresh_mode)
        self.settings_panel.bitrate_check.toggled.connect(self.refresh_mode)

        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background:#07111f;
                color:#d9ecfb;
                font-family:'Segoe UI','Microsoft YaHei UI','PingFang SC';
                font-size:14px;
            }
            QLabel#appHeading {
                color:#f4fbff;
                font-size:27px;
                font-weight:750;
                letter-spacing:.3px;
            }
            QLabel#appSubheading { color:#6fa7c9; font-size:12px; }
            QLabel#statusLabel { color:#91b6cf; padding-left:3px; }
            QLabel#previewDecoderStatus { color:#6eaed4; font-size:12px; }
            QFrame#toolbarFrame {
                background:#091a2d;
                border:1px solid #173b5e;
                border-radius:9px;
            }
            QGroupBox {
                background:#081728;
                border:1px solid #1b456d;
                border-radius:10px;
                margin-top:12px;
                padding-top:10px;
                font-weight:650;
            }
            QGroupBox::title {
                subcontrol-origin:margin;
                left:12px;
                padding:0 6px;
                color:#58d3ff;
            }
            QPushButton, QComboBox, QLineEdit, QSpinBox {
                min-height:22px;
                background:#0d233c;
                border:1px solid #28577e;
                border-radius:6px;
                padding:6px 9px;
                color:#ecf8ff;
                selection-background-color:#087cab;
            }
            QPushButton:hover, QComboBox:hover, QLineEdit:hover, QSpinBox:hover {
                border-color:#00bff3;
                background:#12304f;
            }
            QPushButton:pressed { background:#0b4164; }
            QPushButton:disabled, QComboBox:disabled, QLineEdit:disabled, QSpinBox:disabled {
                color:#61788b;
                background:#091624;
                border-color:#173047;
            }
            QCheckBox { spacing:9px; padding:7px 4px; }
            QCheckBox::indicator {
                width:19px;
                height:19px;
                border:2px solid #3b6f94;
                border-radius:5px;
                background:#081523;
            }
            QCheckBox::indicator:checked {
                background:#00aeea;
                border-color:#62e3ff;
            }
            QListWidget {
                background:#040d18;
                border:1px solid #173b60;
                border-radius:8px;
                padding:5px;
                outline:0;
            }
            QListWidget::item {
                padding:9px 8px;
                border-bottom:1px solid #102b45;
                border-radius:5px;
            }
            QListWidget::item:selected { background:#0a486d; color:#ffffff; }
            QSlider::groove:horizontal {
                height:5px;
                background:#17324b;
                border-radius:2px;
            }
            QSlider::sub-page:horizontal { background:#00aeea; border-radius:2px; }
            QSlider::handle:horizontal {
                width:15px;
                margin:-5px 0;
                border-radius:7px;
                background:#dff8ff;
                border:2px solid #00aeea;
            }
            QProgressBar {
                border:1px solid #28577e;
                border-radius:6px;
                text-align:center;
                background:#06101d;
            }
            QProgressBar::chunk { background:#00aeea; border-radius:5px; }
            QToolTip {
                color:#eaf8ff;
                background:#0b1d31;
                border:1px solid #2b658f;
                padding:5px;
            }
            """
        )

    def retranslate(self) -> None:
        self.setWindowTitle(tr(self.language, "title"))
        self.heading.setText("FrameJoin Studio")
        self.subheading.setText(tr(self.language, "subtitle"))
        self.language_label.setText(tr(self.language, "language"))
        self.media_group.setTitle(tr(self.language, "media"))
        self.preview_group.setTitle(tr(self.language, "preview"))
        for button, key in (
            (self.add_video_button, "add_video"),
            (self.add_sequence_button, "add_sequence"),
            (self.remove_button, "remove"),
            (self.clear_button, "clear"),
            (self.up_button, "up"),
            (self.down_button, "down"),
            (self.save_button, "save_project"),
            (self.load_button, "load_project"),
        ):
            button.setText(tr(self.language, key))
        self.settings_panel.retranslate(self.language)
        self.preview.retranslate(self.language)
        self.status_label.setText(tr(self.language, "status_ready"))
        for index in range(self.media_list.count()):
            self._update_item(self.media_list.item(index))

    def change_language(self, _index: int) -> None:
        language = self.language_combo.currentData()
        if language == self.language:
            return
        answer = QMessageBox.question(
            self,
            tr(self.language, "restart_title"),
            tr(self.language, "confirm_restart"),
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.language_combo.blockSignals(True)
            self.language_combo.setCurrentIndex(self.language_combo.findData(self.language))
            self.language_combo.blockSignals(False)
            return
        self.settings_store.setValue("language", language)
        self.settings_store.sync()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def _sync_preview(self, jump_to_selection: bool = False) -> None:
        clips = self.ordered_clips()
        selected = max(0, self.media_list.currentRow())
        self.preview.set_clips(
            clips,
            selected_index=selected,
            jump_to_selection=jump_to_selection,
        )

    def _selection_changed(self, current, _previous) -> None:
        if current is None:
            self._sync_preview(False)
            return
        self.preview.set_selected_index(self.media_list.row(current), jump=True)

    def _preview_message(self, detail: str) -> None:
        if detail:
            self.status_label.setText(detail)

    def _clear(self) -> None:
        self.media_list.clear()
        self.preview.set_clips([])
        self.refresh_mode()

    def refresh_mode(self, *_args) -> None:
        clips = self.ordered_clips()
        video_mode = bool(clips and clips[0].media_type == "video")
        for widget in (
            self.settings_panel.fps_combo,
            self.settings_panel.apply_fps_button,
            self.settings_panel.codec_combo,
            self.settings_panel.bitrate_check,
        ):
            widget.setEnabled(not video_mode)
        self.settings_panel._mode_changed()
        self.settings_panel.mode_note.setText(
            tr(self.language, "video_mode")
            if video_mode
            else tr(
                self.language,
                "sequence_bitrate"
                if self.settings_panel.bitrate_check.isChecked()
                else "sequence_lossless",
            )
        )
        self._sync_preview(False)
