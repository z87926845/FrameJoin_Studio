from __future__ import annotations

import os
import sys
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QComboBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton, QSplitter, QVBoxLayout, QWidget
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
        if self.language not in LANGUAGES: self.language = "zh_CN"
        self.tools = Toolchain.detect()
        if not self.tools.ffmpeg or not self.tools.ffprobe:
            raise RuntimeError("FFmpeg/ffprobe not found. 请将它们放入 tools/ 或系统 PATH。")
        self.capabilities = EncoderCapabilities.detect(self.tools.ffmpeg)
        self.export_thread = None; self._cpu_fallback_attempted = False
        self.setWindowIcon(application_icon()); self.resize(1320, 820); self.setMinimumSize(980, 650)
        self._build_ui(); self.retranslate(); self.refresh_mode()

    def _build_ui(self) -> None:
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(14, 12, 14, 12)
        header = QHBoxLayout(); self.heading = QLabel("FrameJoin Studio")
        self.heading.setStyleSheet("font-size:24px;font-weight:700;color:#e7f6ff;")
        header.addWidget(self.heading); header.addStretch(1); self.language_label = QLabel(); self.language_combo = QComboBox()
        for code, label in LANGUAGES.items(): self.language_combo.addItem(label, code)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.language))); self.language_combo.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language_label); header.addWidget(self.language_combo); root.addLayout(header)
        toolbar = QHBoxLayout()
        self.add_video_button=QPushButton(); self.add_sequence_button=QPushButton(); self.remove_button=QPushButton(); self.clear_button=QPushButton(); self.up_button=QPushButton(); self.down_button=QPushButton(); self.save_button=QPushButton(); self.load_button=QPushButton()
        for button in (self.add_video_button,self.add_sequence_button,self.remove_button,self.clear_button,self.up_button,self.down_button,self.save_button,self.load_button): toolbar.addWidget(button)
        toolbar.addStretch(1); root.addLayout(toolbar)
        splitter=QSplitter(Qt.Orientation.Horizontal); left=QFrame(); left_layout=QVBoxLayout(left)
        self.media_group=QGroupBox(); media_layout=QVBoxLayout(self.media_group); self.media_list=DropListWidget(); self.media_list.paths_dropped.connect(self.add_paths); self.media_list.currentItemChanged.connect(self._selection_changed); media_layout.addWidget(self.media_list); left_layout.addWidget(self.media_group,2)
        self.preview_group=QGroupBox(); preview_layout=QVBoxLayout(self.preview_group); self.preview=PreviewWidget(self.tools,self.language); preview_layout.addWidget(self.preview); left_layout.addWidget(self.preview_group,3); splitter.addWidget(left)
        self.settings_panel=SettingsPanel(self.capabilities,self.language); self.settings_panel.setMinimumWidth(390); splitter.addWidget(self.settings_panel); splitter.setStretchFactor(0,1); splitter.setStretchFactor(1,0); root.addWidget(splitter,1)
        footer=QHBoxLayout(); self.status_label=QLabel(); self.progress=QProgressBar(); self.progress.setRange(0,1000); self.progress.setMaximumWidth(360); footer.addWidget(self.status_label,1); footer.addWidget(self.progress); root.addLayout(footer)
        self.add_video_button.clicked.connect(self.add_video_dialog); self.add_sequence_button.clicked.connect(self.add_sequence_dialog); self.remove_button.clicked.connect(self.remove_selected); self.clear_button.clicked.connect(self._clear); self.up_button.clicked.connect(lambda:self.move_selected(-1)); self.down_button.clicked.connect(lambda:self.move_selected(1)); self.save_button.clicked.connect(self.save_project); self.load_button.clicked.connect(self.load_project)
        self.settings_panel.browse_requested.connect(self.browse_output); self.settings_panel.start_requested.connect(self.start_export); self.settings_panel.cancel_requested.connect(self.cancel_export); self.settings_panel.fps_apply_requested.connect(self.apply_fps)
        self.settings_panel.container_combo.currentIndexChanged.connect(self.refresh_mode); self.settings_panel.codec_combo.currentIndexChanged.connect(self.refresh_mode); self.settings_panel.bitrate_check.toggled.connect(self.refresh_mode)
        self.setStyleSheet("""QMainWindow,QWidget{background:#07111f;color:#dbeeff;font-family:'Segoe UI','PingFang SC';}QGroupBox{border:1px solid #183a60;border-radius:8px;margin-top:10px;padding-top:8px;font-weight:600;}QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;color:#59d4ff;}QPushButton,QComboBox,QLineEdit,QSpinBox{background:#0d2038;border:1px solid #24547f;border-radius:5px;padding:6px;color:#e8f7ff;}QPushButton:hover{border-color:#00c6ff;background:#123052;}QPushButton:disabled{color:#60768c;border-color:#18324d;}QListWidget{background:#050c17;border:1px solid #173a60;border-radius:7px;padding:4px;}QListWidget::item{padding:7px;border-bottom:1px solid #102943;}QListWidget::item:selected{background:#0c4870;}QProgressBar{border:1px solid #24547f;border-radius:5px;text-align:center;background:#06101d;}QProgressBar::chunk{background:#00aeea;}""")

    def retranslate(self) -> None:
        self.setWindowTitle(tr(self.language,"title")); self.heading.setText(tr(self.language,"title")); self.language_label.setText(tr(self.language,"language")); self.media_group.setTitle(tr(self.language,"media")); self.preview_group.setTitle(tr(self.language,"preview"))
        for button,key in ((self.add_video_button,"add_video"),(self.add_sequence_button,"add_sequence"),(self.remove_button,"remove"),(self.clear_button,"clear"),(self.up_button,"up"),(self.down_button,"down"),(self.save_button,"save_project"),(self.load_button,"load_project")): button.setText(tr(self.language,key))
        self.settings_panel.retranslate(self.language); self.preview.retranslate(self.language); self.status_label.setText(tr(self.language,"status_ready"))
        for index in range(self.media_list.count()): self._update_item(self.media_list.item(index))

    def change_language(self,_index:int)->None:
        language=self.language_combo.currentData()
        if language==self.language:return
        answer=QMessageBox.question(self,tr(self.language,"restart_title"),tr(self.language,"confirm_restart"))
        if answer!=QMessageBox.StandardButton.Yes:
            self.language_combo.blockSignals(True); self.language_combo.setCurrentIndex(self.language_combo.findData(self.language)); self.language_combo.blockSignals(False); return
        self.settings_store.setValue("language",language); self.settings_store.sync(); os.execl(sys.executable,sys.executable,*sys.argv)

    def _selection_changed(self,current,_previous)->None:
        self.preview.set_clip(current.data(Qt.ItemDataRole.UserRole) if current else None)

    def _clear(self)->None:
        self.media_list.clear(); self.preview.set_clip(None); self.refresh_mode()

    def refresh_mode(self,*_args)->None:
        clips=self.ordered_clips(); video_mode=bool(clips and clips[0].media_type=="video")
        for widget in (self.settings_panel.fps_combo,self.settings_panel.apply_fps_button,self.settings_panel.codec_combo,self.settings_panel.bitrate_check,self.settings_panel.bitrate_spin,self.settings_panel.backend_combo): widget.setEnabled(not video_mode)
        self.settings_panel.lossy_options.setVisible(not video_mode and self.settings_panel.bitrate_check.isChecked() and self.settings_panel.codec_combo.currentData() != "ffv1")
        self.settings_panel.mode_note.setText(tr(self.language,"video_mode") if video_mode else tr(self.language,"sequence_bitrate" if self.settings_panel.bitrate_check.isChecked() else "sequence_lossless"))
