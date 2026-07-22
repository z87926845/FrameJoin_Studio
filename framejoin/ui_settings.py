from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget
from .i18n import tr
from .models import JoinSettings
from .tools import EncoderCapabilities


class SettingsPanel(QGroupBox):
    browse_requested = Signal()
    start_requested = Signal()
    cancel_requested = Signal()
    fps_apply_requested = Signal(str)

    def __init__(self, capabilities: EncoderCapabilities, language: str = "zh_CN", parent=None) -> None:
        super().__init__(parent)
        self.capabilities = capabilities
        self.language = language
        self.fps_edit = QLineEdit("24")
        self.apply_fps_button = QPushButton()
        fps_row = QWidget()
        fps_layout = QHBoxLayout(fps_row)
        fps_layout.setContentsMargins(0, 0, 0, 0)
        fps_layout.addWidget(self.fps_edit, 1)
        fps_layout.addWidget(self.apply_fps_button)
        self.container_combo = QComboBox()
        for text, data in (("MP4", "mp4"), ("MOV", "mov"), ("MKV", "mkv"), ("Auto / 跟随源", "auto")):
            self.container_combo.addItem(text, data)
        self.codec_combo = QComboBox()
        self.codec_combo.addItem("", "h264_lossless")
        self.codec_combo.addItem("", "h265_lossless")
        self.codec_combo.addItem("", "ffv1")
        self.bitrate_check = QCheckBox()
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1, 1000)
        self.bitrate_spin.setValue(100)
        self.bitrate_spin.setSuffix(" Mbps")
        self.backend_combo = QComboBox()
        self.output_edit = QLineEdit()
        self.browse_button = QPushButton()
        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_edit, 1)
        output_layout.addWidget(self.browse_button)
        self.mode_note = QLabel()
        self.mode_note.setWordWrap(True)
        self.estimate_label = QLabel()
        self.start_button = QPushButton()
        self.cancel_button = QPushButton()
        self.cancel_button.setEnabled(False)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(self.cancel_button)
        self.form = QFormLayout()
        self.form.addRow("", fps_row)
        self.form.addRow("", self.container_combo)
        self.form.addRow("", self.codec_combo)
        self.form.addRow("", self.bitrate_check)
        self.form.addRow("", self.bitrate_spin)
        self.form.addRow("", self.backend_combo)
        self.form.addRow("", output_row)
        body = QVBoxLayout(self)
        body.addLayout(self.form)
        body.addWidget(self.mode_note)
        body.addWidget(self.estimate_label)
        body.addStretch(1)
        body.addLayout(buttons)
        self.apply_fps_button.clicked.connect(lambda: self.fps_apply_requested.emit(self.fps_edit.text().strip()))
        self.browse_button.clicked.connect(self.browse_requested)
        self.start_button.clicked.connect(self.start_requested)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.codec_combo.currentIndexChanged.connect(self.refresh_backends)
        self.bitrate_check.toggled.connect(self._mode_changed)
        self.bitrate_spin.valueChanged.connect(self._mode_changed)
        self.retranslate(language)
        self._mode_changed()

    def retranslate(self, language: str) -> None:
        self.language = language
        self.setTitle(tr(language, "output"))
        self.apply_fps_button.setText(tr(language, "apply_fps"))
        self.bitrate_check.setText(tr(language, "bitrate_enable"))
        self.browse_button.setText(tr(language, "browse"))
        self.start_button.setText(tr(language, "start"))
        self.cancel_button.setText(tr(language, "cancel"))
        labels = ["fps", "container", "codec", "", "bitrate", "backend", "output"]
        for row, key in enumerate(labels):
            item = self.form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item and item.widget():
                item.widget().setText(tr(language, key) if key else "")
        for index, key in enumerate(("h264", "h265", "ffv1")):
            self.codec_combo.setItemText(index, tr(language, key))
        self.refresh_backends(keep=self.backend_combo.currentData())
        self._mode_changed()

    def refresh_backends(self, _index: int = -1, keep: str | None = None) -> None:
        selected = keep or self.backend_combo.currentData() or "auto"
        codec = self.codec_combo.currentData()
        self.backend_combo.blockSignals(True)
        self.backend_combo.clear()
        self.backend_combo.addItem(tr(self.language, "auto"), "auto")
        self.backend_combo.addItem(tr(self.language, "cpu"), "cpu")
        for backend in self.capabilities.available_hardware_backends(codec):
            self.backend_combo.addItem(tr(self.language, backend), backend)
        found = self.backend_combo.findData(selected)
        self.backend_combo.setCurrentIndex(found if found >= 0 else 0)
        self.backend_combo.blockSignals(False)
        self._mode_changed()

    def _mode_changed(self, *_args) -> None:
        lossless = not self.bitrate_check.isChecked()
        ffv1 = self.codec_combo.currentData() == "ffv1"
        if ffv1 and self.bitrate_check.isChecked():
            self.bitrate_check.blockSignals(True)
            self.bitrate_check.setChecked(False)
            self.bitrate_check.blockSignals(False)
            lossless = True
        self.bitrate_check.setEnabled(not ffv1)
        self.bitrate_spin.setEnabled(not lossless and not ffv1)
        self.backend_combo.setEnabled(not lossless and not ffv1)
        self.mode_note.setText(tr(self.language, "sequence_lossless" if lossless else "sequence_bitrate"))

    def settings(self, video_mode: bool) -> JoinSettings:
        return JoinSettings(container=self.container_combo.currentData() or "auto", faststart=True, sequence_codec=self.codec_combo.currentData(), sequence_bitrate_enabled=self.bitrate_check.isChecked(), sequence_bitrate_mbps=self.bitrate_spin.value(), sequence_encoder_backend=self.backend_combo.currentData() or "auto")

    def load_settings(self, settings: JoinSettings) -> None:
        for combo, data in ((self.container_combo, settings.container), (self.codec_combo, settings.sequence_codec)):
            index = combo.findData(data)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.bitrate_check.setChecked(settings.sequence_bitrate_enabled)
        self.bitrate_spin.setValue(settings.sequence_bitrate_mbps)
        self.refresh_backends(keep=settings.sequence_encoder_backend)

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
