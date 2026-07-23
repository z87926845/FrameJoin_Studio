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


def _editable_fps_combo(default: str = "24") -> QComboBox:
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.setMaxVisibleItems(12)
    for label, value in FPS_PRESETS:
        combo.addItem(label, value)
    combo.setCurrentIndex(combo.findData(default))
    return combo


class SettingsPanel(QGroupBox):
    browse_requested = Signal()
    start_requested = Signal()
    cancel_requested = Signal()
    fps_apply_requested = Signal(str)
    mode_changed = Signal()

    def __init__(self, capabilities: EncoderCapabilities, language: str = "zh_CN", parent=None) -> None:
        super().__init__(parent)
        self.capabilities = capabilities
        self.language = language
        self.video_mode = False

        self.sequence_mode_label = QLabel()
        self.sequence_mode_combo = QComboBox()
        self.sequence_mode_combo.addItem("", "video")
        self.sequence_mode_combo.addItem("", "frames")

        self.fps_label = QLabel()
        self.fps_combo = _editable_fps_combo()
        self.apply_fps_button = QPushButton()
        self.fps_row = QWidget()
        fps_layout = QHBoxLayout(self.fps_row)
        fps_layout.setContentsMargins(0, 0, 0, 0)
        fps_layout.addWidget(self.fps_combo, 1)
        fps_layout.addWidget(self.apply_fps_button)

        self.container_label = QLabel()
        self.container_combo = QComboBox()
        for text, data in (
            ("MP4", "mp4"),
            ("MOV", "mov"),
            ("MKV", "mkv"),
            ("Auto / 跟随源", "auto"),
        ):
            self.container_combo.addItem(text, data)

        self.codec_label = QLabel()
        self.codec_combo = QComboBox()
        self.codec_combo.addItem("", "h264_lossless")
        self.codec_combo.addItem("", "h265_lossless")
        self.codec_combo.addItem("", "ffv1")

        self.lossy_card = QFrame()
        self.lossy_card.setObjectName("optionCard")
        lossy_card_layout = QVBoxLayout(self.lossy_card)
        lossy_card_layout.setContentsMargins(12, 9, 12, 10)
        lossy_card_layout.setSpacing(5)
        self.bitrate_check = QCheckBox()
        self.bitrate_check.setObjectName("strongCheck")
        lossy_card_layout.addWidget(self.bitrate_check)
        self.lossy_options = QWidget()
        self.lossy_form = QFormLayout(self.lossy_options)
        self.lossy_form.setContentsMargins(22, 2, 0, 0)
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

        self.frame_card = QFrame()
        self.frame_card.setObjectName("optionCard")
        frame_form = QFormLayout(self.frame_card)
        frame_form.setContentsMargins(12, 10, 12, 10)
        self.frame_prefix_label = QLabel()
        self.frame_prefix_edit = QLineEdit("frame_")
        self.frame_start_label = QLabel()
        self.frame_start_spin = QSpinBox()
        self.frame_start_spin.setRange(0, 999_999_999)
        self.frame_start_spin.setValue(1)
        self.frame_digits_label = QLabel()
        self.frame_digits_spin = QSpinBox()
        self.frame_digits_spin.setRange(1, 12)
        self.frame_digits_spin.setValue(6)
        self.frame_note = QLabel()
        self.frame_note.setWordWrap(True)
        self.frame_note.setObjectName("gpuStatusLabel")
        frame_form.addRow(self.frame_prefix_label, self.frame_prefix_edit)
        frame_form.addRow(self.frame_start_label, self.frame_start_spin)
        frame_form.addRow(self.frame_digits_label, self.frame_digits_spin)
        frame_form.addRow("", self.frame_note)

        self.video_card = QFrame()
        self.video_card.setObjectName("optionCard")
        video_layout = QVBoxLayout(self.video_card)
        video_layout.setContentsMargins(12, 9, 12, 10)
        video_layout.setSpacing(5)
        self.video_transcode_check = QCheckBox()
        self.video_transcode_check.setObjectName("strongCheck")
        video_layout.addWidget(self.video_transcode_check)
        self.video_options = QWidget()
        video_form = QFormLayout(self.video_options)
        video_form.setContentsMargins(22, 2, 0, 0)
        self.video_codec_label = QLabel()
        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItem("H.264", "h264")
        self.video_codec_combo.addItem("H.265", "h265")
        self.video_bitrate_label = QLabel()
        self.video_bitrate_spin = QSpinBox()
        self.video_bitrate_spin.setRange(1, 1000)
        self.video_bitrate_spin.setValue(100)
        self.video_bitrate_spin.setSuffix(" Mbps")
        self.video_backend_label = QLabel()
        self.video_backend_combo = QComboBox()
        self.video_backend_combo.setMinimumContentsLength(24)
        self.video_fps_mode_label = QLabel()
        self.video_fps_mode_combo = QComboBox()
        self.video_fps_mode_combo.addItem("", "source")
        self.video_fps_mode_combo.addItem("", "custom")
        self.video_fps_label = QLabel()
        self.video_fps_combo = _editable_fps_combo()
        self.video_audio_label = QLabel()
        self.video_audio_combo = QComboBox()
        self.video_audio_combo.addItem("", "aac")
        self.video_audio_combo.addItem("", "copy")
        self.video_audio_combo.addItem("", "none")
        self.video_gpu_status_label = QLabel()
        self.video_gpu_status_label.setWordWrap(True)
        self.video_gpu_status_label.setObjectName("gpuStatusLabel")
        video_form.addRow(self.video_codec_label, self.video_codec_combo)
        video_form.addRow(self.video_bitrate_label, self.video_bitrate_spin)
        video_form.addRow(self.video_backend_label, self.video_backend_combo)
        video_form.addRow(self.video_fps_mode_label, self.video_fps_mode_combo)
        video_form.addRow(self.video_fps_label, self.video_fps_combo)
        video_form.addRow(self.video_audio_label, self.video_audio_combo)
        video_form.addRow("", self.video_gpu_status_label)
        video_layout.addWidget(self.video_options)

        self.output_label = QLabel()
        self.output_edit = QLineEdit()
        self.browse_button = QPushButton()
        self.output_row = QWidget()
        output_layout = QHBoxLayout(self.output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_edit, 1)
        output_layout.addWidget(self.browse_button)

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
        self.form.addRow(self.sequence_mode_label, self.sequence_mode_combo)
        self.form.addRow(self.fps_label, self.fps_row)
        self.form.addRow(self.container_label, self.container_combo)
        self.form.addRow(self.codec_label, self.codec_combo)
        self.form.addRow("", self.lossy_card)
        self.form.addRow("", self.frame_card)
        self.form.addRow("", self.video_card)
        self.form.addRow(self.output_label, self.output_row)

        body = QVBoxLayout(self)
        body.setContentsMargins(13, 15, 13, 13)
        body.addLayout(self.form)
        body.addWidget(self.mode_note)
        body.addWidget(self.estimate_label)
        body.addStretch(1)
        body.addLayout(buttons)

        self.setStyleSheet(
            """
            QFrame#optionCard {
                background:#091b2d;
                border:1px solid #234d70;
                border-radius:9px;
            }
            QCheckBox#strongCheck {
                color:#8ee7ff;
                font-size:15px;
                font-weight:700;
                padding:7px 5px;
            }
            QCheckBox#strongCheck:disabled { color:#667f91; }
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
        for signal in (
            self.sequence_mode_combo.currentIndexChanged,
            self.codec_combo.currentIndexChanged,
            self.bitrate_check.toggled,
            self.video_transcode_check.toggled,
            self.video_codec_combo.currentIndexChanged,
            self.video_fps_mode_combo.currentIndexChanged,
        ):
            signal.connect(self._mode_changed)
        self.retranslate(language)
        self._mode_changed()

    @staticmethod
    def _fps_value(combo: QComboBox) -> str:
        text = combo.currentText().strip()
        index = combo.currentIndex()
        if index >= 0 and text == combo.itemText(index):
            return str(combo.itemData(index) or text)
        return text or "24"

    @staticmethod
    def _set_fps_value(combo: QComboBox, value: str) -> None:
        value = str(value or "24").strip()
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setEditText(value)

    def fps_value(self) -> str:
        return self._fps_value(self.fps_combo)

    def set_fps_value(self, value: str) -> None:
        self._set_fps_value(self.fps_combo, value)

    def video_fps_value(self) -> str:
        return self._fps_value(self.video_fps_combo)

    def _emit_fps(self) -> None:
        self.fps_apply_requested.emit(self.fps_value())

    def retranslate(self, language: str) -> None:
        self.language = language
        self.setTitle(tr(language, "output"))
        self.sequence_mode_label.setText(tr(language, "sequence_output_mode"))
        self.sequence_mode_combo.setItemText(0, tr(language, "sequence_to_video"))
        self.sequence_mode_combo.setItemText(1, tr(language, "sequence_to_frames"))
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
        self.frame_prefix_label.setText(tr(language, "frame_prefix"))
        self.frame_start_label.setText(tr(language, "frame_start"))
        self.frame_digits_label.setText(tr(language, "frame_digits"))
        self.frame_note.setText(tr(language, "frame_copy_note"))
        self.video_transcode_check.setText(tr(language, "video_transcode_enable"))
        self.video_transcode_check.setToolTip(tr(language, "video_transcode_hint"))
        self.video_codec_label.setText(tr(language, "video_codec"))
        self.video_bitrate_label.setText(tr(language, "bitrate"))
        self.video_backend_label.setText(tr(language, "backend"))
        self.video_fps_mode_label.setText(tr(language, "video_fps_mode"))
        self.video_fps_mode_combo.setItemText(0, tr(language, "video_fps_source"))
        self.video_fps_mode_combo.setItemText(1, tr(language, "video_fps_custom"))
        self.video_fps_label.setText(tr(language, "fps"))
        self.video_audio_label.setText(tr(language, "video_audio"))
        self.video_audio_combo.setItemText(0, tr(language, "audio_aac"))
        self.video_audio_combo.setItemText(1, tr(language, "audio_copy"))
        self.video_audio_combo.setItemText(2, tr(language, "audio_none"))
        self.browse_button.setText(tr(language, "browse"))
        self.start_button.setText(tr(language, "start"))
        self.cancel_button.setText(tr(language, "cancel"))
        for index, key in enumerate(("h264", "h265", "ffv1")):
            self.codec_combo.setItemText(index, tr(language, key))
        self.refresh_backends()
        self._mode_changed()

    def _backend_names(self) -> tuple[str, ...]:
        return ("videotoolbox",) if sys.platform == "darwin" else ("nvenc", "qsv", "amf")

    def _populate_backend_combo(self, combo: QComboBox, codec_key: str, status: QLabel, keep: str | None = None) -> None:
        selected = keep or combo.currentData() or "auto"
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr(self.language, "auto"), "auto")
        combo.addItem(tr(self.language, "cpu"), "cpu")
        available_count = 0
        for backend in self._backend_names():
            available = self.capabilities.backend_available(backend, codec_key)
            label = tr(self.language, backend)
            if not available:
                label = f"{label} · {tr(self.language, 'gpu_unavailable')}"
            combo.addItem(label, backend)
            item = combo.model().item(combo.count() - 1)
            if item is not None:
                item.setEnabled(available)
                item.setToolTip(
                    tr(self.language, "gpu_available_hint")
                    if available
                    else tr(self.language, "gpu_unavailable_hint")
                )
            available_count += int(available)
        found = combo.findData(selected)
        if found >= 0 and combo.model().item(found).isEnabled():
            combo.setCurrentIndex(found)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
        status.setText(
            tr(self.language, "gpu_detected", count=available_count)
            if available_count
            else tr(self.language, "gpu_none_detected")
        )

    def refresh_backends(self, *_args, keep: str | None = None) -> None:
        self._populate_backend_combo(
            self.backend_combo,
            str(self.codec_combo.currentData() or "h264_lossless"),
            self.gpu_status_label,
            keep,
        )
        video_key = "h264_lossless" if self.video_codec_combo.currentData() == "h264" else "h265_lossless"
        self._populate_backend_combo(
            self.video_backend_combo,
            video_key,
            self.video_gpu_status_label,
            keep,
        )

    def set_video_mode(self, video_mode: bool) -> None:
        self.video_mode = bool(video_mode)
        self._mode_changed()

    def output_is_directory(self) -> bool:
        return not self.video_mode and self.sequence_mode_combo.currentData() == "frames"

    def _set_visible(self, visible: bool, *widgets: QWidget) -> None:
        for widget in widgets:
            widget.setVisible(visible)

    def _mode_changed(self, *_args) -> None:
        self.refresh_backends(keep=None) if self.sender() in {self.codec_combo, self.video_codec_combo} else None
        if self.video_mode:
            self._set_visible(False, self.sequence_mode_label, self.sequence_mode_combo, self.fps_label, self.fps_row, self.codec_label, self.codec_combo, self.lossy_card, self.frame_card)
            self._set_visible(True, self.container_label, self.container_combo, self.video_card)
            transcode = self.video_transcode_check.isChecked()
            self.video_options.setEnabled(transcode)
            self.video_fps_combo.setEnabled(transcode and self.video_fps_mode_combo.currentData() == "custom")
            self.mode_note.setText(tr(self.language, "video_transcode_mode" if transcode else "video_mode"))
        else:
            self._set_visible(True, self.sequence_mode_label, self.sequence_mode_combo, self.fps_label, self.fps_row)
            self.video_card.setVisible(False)
            frame_mode = self.sequence_mode_combo.currentData() == "frames"
            self._set_visible(not frame_mode, self.container_label, self.container_combo, self.codec_label, self.codec_combo, self.lossy_card)
            self.frame_card.setVisible(frame_mode)
            ffv1 = self.codec_combo.currentData() == "ffv1"
            if ffv1 and self.bitrate_check.isChecked():
                self.bitrate_check.blockSignals(True)
                self.bitrate_check.setChecked(False)
                self.bitrate_check.blockSignals(False)
            lossy = self.bitrate_check.isChecked() and not ffv1 and not frame_mode
            self.bitrate_check.setEnabled(not ffv1 and not frame_mode)
            self.lossy_options.setEnabled(lossy)
            if frame_mode:
                self.mode_note.setText(tr(self.language, "sequence_frames_mode"))
            else:
                self.mode_note.setText(tr(self.language, "sequence_bitrate" if lossy else "sequence_lossless"))
        self.output_label.setText(tr(self.language, "output_folder" if self.output_is_directory() else "output"))
        active_lossy = (
            self.video_mode and self.video_transcode_check.isChecked()
        ) or (
            not self.video_mode and self.sequence_mode_combo.currentData() == "video" and self.bitrate_check.isChecked()
        )
        self.mode_note.setStyleSheet(
            "color:#ffcb6b;padding:6px 3px;" if active_lossy else "color:#85abc5;padding:6px 3px;"
        )
        self.mode_changed.emit()

    def settings(self, video_mode: bool) -> JoinSettings:
        return JoinSettings(
            container=self.container_combo.currentData() or "auto",
            faststart=True,
            sequence_output_mode=self.sequence_mode_combo.currentData() or "video",
            sequence_codec=self.codec_combo.currentData() or "h264_lossless",
            sequence_bitrate_enabled=(not video_mode and self.sequence_mode_combo.currentData() == "video" and self.bitrate_check.isChecked()),
            sequence_bitrate_mbps=self.bitrate_spin.value(),
            sequence_encoder_backend=self.backend_combo.currentData() or "auto",
            sequence_frame_prefix=self.frame_prefix_edit.text().strip() or "frame_",
            sequence_frame_start=self.frame_start_spin.value(),
            sequence_frame_digits=self.frame_digits_spin.value(),
            video_transcode_enabled=(video_mode and self.video_transcode_check.isChecked()),
            video_codec=self.video_codec_combo.currentData() or "h264",
            video_bitrate_mbps=self.video_bitrate_spin.value(),
            video_encoder_backend=self.video_backend_combo.currentData() or "auto",
            video_fps_mode=self.video_fps_mode_combo.currentData() or "source",
            video_fps=self.video_fps_value(),
            video_audio_mode=self.video_audio_combo.currentData() or "aac",
        )

    def load_settings(self, settings: JoinSettings) -> None:
        for combo, data in (
            (self.container_combo, settings.container),
            (self.sequence_mode_combo, settings.sequence_output_mode),
            (self.codec_combo, settings.sequence_codec),
            (self.video_codec_combo, settings.video_codec),
            (self.video_fps_mode_combo, settings.video_fps_mode),
            (self.video_audio_combo, settings.video_audio_mode),
        ):
            index = combo.findData(data)
            if index >= 0:
                combo.setCurrentIndex(index)
        self.bitrate_check.setChecked(bool(settings.sequence_bitrate_enabled))
        self.bitrate_spin.setValue(settings.sequence_bitrate_mbps)
        self.frame_prefix_edit.setText(settings.sequence_frame_prefix)
        self.frame_start_spin.setValue(settings.sequence_frame_start)
        self.frame_digits_spin.setValue(settings.sequence_frame_digits)
        self.video_transcode_check.setChecked(bool(settings.video_transcode_enabled))
        self.video_bitrate_spin.setValue(settings.video_bitrate_mbps)
        self._set_fps_value(self.video_fps_combo, settings.video_fps)
        self.refresh_backends(keep=settings.sequence_encoder_backend)
        video_index = self.video_backend_combo.findData(settings.video_encoder_backend)
        if video_index >= 0 and self.video_backend_combo.model().item(video_index).isEnabled():
            self.video_backend_combo.setCurrentIndex(video_index)
        self._mode_changed()

    def set_running(self, running: bool) -> None:
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)


def QtAlignmentRight():
    from PySide6.QtCore import Qt

    return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
