from __future__ import annotations

import sys

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .i18n import tr
from .models import JoinSettings
from .tools import EncoderCapabilities


FPS_PRESETS = (
    ("23.976 (24000/1001)", "24000/1001"),
    ("24", "24"),
    ("25", "25"),
    ("29.97 (30000/1001)", "30000/1001"),
    ("30", "30"),
    ("50", "50"),
    ("59.94 (60000/1001)", "60000/1001"),
    ("60", "60"),
    ("120", "120"),
)


class SettingsPanel(QGroupBox):
    browse_requested = Signal()
    start_requested = Signal()
    cancel_requested = Signal()
    fps_apply_requested = Signal(str)

    def __init__(self, capabilities: EncoderCapabilities, language: str = "zh_CN", parent=None) -> None:
        super().__init__(parent)
        self.capabilities = capabilities
        self.language = language
        self.video_mode = False

        self.fps_combo = QComboBox()
        self.fps_combo.setEditable(True)
        self.fps_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.fps_combo.setMaxVisibleItems(12)
        for label, value in FPS_PRESETS:
            self.fps_combo.addItem(label, value)
        self.fps_combo.setCurrentIndex(self.fps_combo.findData("24"))
        self.apply_fps_button = QPushButton()
        fps_row = QWidget()
        fps_layout = QHBoxLayout(fps_row)
        fps_layout.setContentsMargins(0, 0, 0, 0)
        fps_layout.addWidget(self.fps_combo, 1)
        fps_layout.addWidget(self.apply_fps_button)

        self.container_combo = QComboBox()
        for text, data in (
            ("MP4", "mp4"),
            ("MOV", "mov"),
            ("MKV", "mkv"),
            ("Auto / 跟随源", "auto"),
        ):
            self.container_combo.addItem(text, data)

        self.codec_combo = QComboBox()
        self.codec_combo.addItem("", "h264_lossless")
        self.codec_combo.addItem("", "h265_lossless")
        self.codec_combo.addItem("", "ffv1")

        self.lossy_card = QFrame()
        self.lossy_card.setObjectName("lossyCard")
        lossy_card_layout = QVBoxLayout(self.lossy_card)
        lossy_card_layout.setContentsMargins(12, 9, 12, 10)
        lossy_card_layout.setSpacing(5)

        self.bitrate_check = QCheckBox()
        self.bitrate_check.setObjectName("lossyEnableCheck")
        self.bitrate_check.setChecked(False)
        lossy_card_layout.addWidget(self.bitrate_check)

        self.lossy_options = QWidget()
        self.lossy_form = QFormLayout(self.lossy_options)
        self.lossy_form.setContentsMargins(22, 2, 0, 0)
        self.lossy_form.setHorizontalSpacing(12)
        self.lossy_form.setVerticalSpacing(7)
        self.bitrate_label = QLabel()
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1, 1000)
        self.bitrate_spin.setValue(100)
        self.bitrate_spin.setSuffix(" Mbps")
        self.backend_label = QLabel()
        self.backend_combo = QComboBox()
        self.backend_combo.setMinimumContentsLength(24)
        self.gpu_status_label = QLabel()
        self.gpu_status_label.setWordWrap(True)
        self.gpu_status_label.setObjectName("gpuStatusLabel")
        self.lossy_form.addRow(self.bitrate_label, self.bitrate_spin)
        self.lossy_form.addRow(self.backend_label, self.backend_combo)
        self.lossy_form.addRow("", self.gpu_status_label)
        lossy_card_layout.addWidget(self.lossy_options)

        self.output_edit = QLineEdit()
        self.browse_button = QPushButton()
        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_edit, 1)
        output_layout.addWidget(self.browse_button)

        self.fps_label = QLabel()
        self.container_label = QLabel()
        self.codec_label = QLabel()
        self.output_label = QLabel()
        self.mode_note = QLabel()
        self.mode_note.setWordWrap(True)
        self.estimate_label = QLabel()
        self.start_button = QPushButton()
        self.start_button.setObjectName("primaryExportButton")
        self.cancel_button = QPushButton()
        self.cancel_button.setEnabled(False)

        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(self.cancel_button)

        self.form = QFormLayout()
        self.form.setLabelAlignment(QtAlignmentRight())
        self.form.setHorizontalSpacing(13)
        self.form.setVerticalSpacing(9)
        self.form.addRow(self.fps_label, fps_row)
        self.form.addRow(self.container_label, self.container_combo)
        self.form.addRow(self.codec_label, self.codec_combo)
        self.form.addRow("", self.lossy_card)
        self.form.addRow(self.output_label, output_row)

        body = QVBoxLayout(self)
        body.setContentsMargins(13, 15, 13, 13)
        body.addLayout(self.form)
        body.addWidget(self.mode_note)
        body.addWidget(self.estimate_label)
        body.addStretch(1)
        body.addLayout(buttons)

        self.setStyleSheet(
            """
            QFrame#lossyCard {
                background:#091b2d;
                border:1px solid #234d70;
                border-radius:9px;
            }
            QFrame#lossyCard:disabled {
                background:#081522;
                border-color:#17344c;
            }
            QCheckBox#lossyEnableCheck {
                color:#8ee7ff;
                font-size:15px;
                font-weight:700;
                padding:7px 5px;
            }
            QCheckBox#lossyEnableCheck:disabled { color:#667f91; }
            QLabel#gpuStatusLabel { color:#6f9bb8; font-size:12px; padding-top:2px; }
            QPushButton#primaryExportButton {
                min-height:31px;
                background:#087aa7;
                border-color:#19cfff;
                font-size:15px;
                font-weight:700;
            }
            QPushButton#primaryExportButton:hover { background:#0795c9; }
            """
        )

        self.apply_fps_button.clicked.connect(self._emit_fps)
        self.browse_button.clicked.connect(self.browse_requested)
        self.start_button.clicked.connect(self.start_requested)
        self.cancel_button.clicked.connect(self.cancel_requested)
        self.codec_combo.currentIndexChanged.connect(self.refresh_backends)
        self.bitrate_check.toggled.connect(self._mode_changed)
        self.bitrate_spin.valueChanged.connect(self._mode_changed)
        self.retranslate(language)
        self._mode_changed()

    def fps_value(self) -> str:
        text = self.fps_combo.currentText().strip()
        index = self.fps_combo.currentIndex()
        if index >= 0 and text == self.fps_combo.itemText(index):
            return str(self.fps_combo.itemData(index) or text)
        return text or "24"

    def set_fps_value(self, value: str) -> None:
        value = str(value or "24").strip()
        index = self.fps_combo.findData(value)
        if index >= 0:
            self.fps_combo.setCurrentIndex(index)
        else:
            self.fps_combo.setEditText(value)

    def _emit_fps(self) -> None:
        self.fps_apply_requested.emit(self.fps_value())

    def retranslate(self, language: str) -> None:
        self.language = language
        self.setTitle(tr(language, "output"))
        self.fps_label.setText(tr(language, "fps"))
        self.container_label.setText(tr(language, "container"))
        self.codec_label.setText(tr(language, "codec"))
        self.output_label.setText(tr(language, "output"))
        self.bitrate_label.setText(tr(language, "bitrate"))
        self.backend_label.setText(tr(language, "backend"))
        self.apply_fps_button.setText(tr(language, "apply_fps"))
        self.fps_combo.setToolTip(tr(language, "fps_hint"))
        self.bitrate_check.setText(tr(language, "bitrate_enable"))
        self.bitrate_check.setToolTip(tr(language, "bitrate_enable_hint"))
        self.browse_button.setText(tr(language, "browse"))
        self.start_button.setText(tr(language, "start"))
        self.cancel_button.setText(tr(language, "cancel"))
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

        backends = (
            ("videotoolbox",)
            if sys.platform == "darwin"
            else ("nvenc", "qsv", "amf")
        )
        available_count = 0
        for backend in backends:
            available = self.capabilities.backend_available(backend, codec)
            label = tr(self.language, backend)
            if not available:
                label = f"{label} · {tr(self.language, 'gpu_unavailable')}"
            self.backend_combo.addItem(label, backend)
            item = self.backend_combo.model().item(self.backend_combo.count() - 1)
            if item is not None:
                item.setEnabled(available)
                item.setToolTip(
                    tr(self.language, "gpu_available_hint")
                    if available
                    else tr(self.language, "gpu_unavailable_hint")
                )
            if available:
                available_count += 1

        found = self.backend_combo.findData(selected)
        if found >= 0 and self.backend_combo.model().item(found).isEnabled():
            self.backend_combo.setCurrentIndex(found)
        else:
            self.backend_combo.setCurrentIndex(0)
        self.backend_combo.blockSignals(False)
        self.gpu_status_label.setText(
            tr(self.language, "gpu_detected", count=available_count)
            if available_count
            else tr(self.language, "gpu_none_detected")
        )
        self._mode_changed()

    def set_video_mode(self, video_mode: bool) -> None:
        self.video_mode = bool(video_mode)
        self._mode_changed()

    def _mode_changed(self, *_args) -> None:
        ffv1 = self.codec_combo.currentData() == "ffv1"
        if ffv1 and self.bitrate_check.isChecked():
            self.bitrate_check.blockSignals(True)
            self.bitrate_check.setChecked(False)
            self.bitrate_check.blockSignals(False)

        lossy = self.bitrate_check.isChecked() and not ffv1 and not self.video_mode
        self.bitrate_check.setEnabled(not ffv1 and not self.video_mode)
        self.lossy_options.setVisible(True)
        self.lossy_options.setEnabled(lossy)
        self.bitrate_spin.setEnabled(lossy)
        self.backend_combo.setEnabled(lossy)
        self.gpu_status_label.setEnabled(lossy)
        self.mode_note.setText(
            tr(self.language, "video_mode")
            if self.video_mode
            else tr(self.language, "sequence_bitrate" if lossy else "sequence_lossless")
        )
        self.mode_note.setStyleSheet(
            "color:#ffcb6b;padding:6px 3px;"
            if lossy
            else "color:#85abc5;padding:6px 3px;"
        )

    def settings(self, video_mode: bool) -> JoinSettings:
        return JoinSettings(
            container=self.container_combo.currentData() or "auto",
            faststart=True,
            sequence_codec=self.codec_combo.currentData(),
            sequence_bitrate_enabled=(not video_mode and self.bitrate_check.isChecked()),
            sequence_bitrate_mbps=self.bitrate_spin.value(),
            sequence_encoder_backend=self.backend_combo.currentData() or "auto",
        )

    def load_settings(self, settings: JoinSettings) -> None:
        for combo, data in (
            (self.container_combo, settings.container),
            (self.codec_combo, settings.sequence_codec),
        ):
            index = combo.findData(data)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.bitrate_check.setChecked(bool(settings.sequence_bitrate_enabled))
        self.bitrate_spin.setValue(settings.sequence_bitrate_mbps)
        self.refresh_backends(keep=settings.sequence_encoder_backend)
        self._mode_changed()

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)


def QtAlignmentRight():
    # Kept as a tiny helper so this module does not need another broad Qt import.
    from PySide6.QtCore import Qt

    return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
