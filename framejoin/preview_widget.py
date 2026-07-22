from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from .i18n import tr
from .models import MediaClip
from .tools import Toolchain, hidden_subprocess_kwargs


class PreviewWidget(QWidget):
    message = Signal(str)

    def __init__(self, tools: Toolchain, language: str = "zh_CN", parent=None) -> None:
        super().__init__(parent)
        self.tools = tools
        self.language = language
        self.clip: MediaClip | None = None
        self.frame = 0
        self.playing = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumSize(480, 270)
        self.canvas.setStyleSheet("background:#030914;border:1px solid #16365a;border-radius:8px;color:#7e96ad;")
        self.canvas.setScaledContents(False)
        self.prev_button = QPushButton()
        self.play_button = QPushButton()
        self.next_button = QPushButton()
        self.prev_button.clicked.connect(lambda: self.step(-1))
        self.play_button.clicked.connect(self.toggle_play)
        self.next_button.clicked.connect(lambda: self.step(1))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self._slider_changed)
        self.counter = QLabel("0 / 0")
        controls = QHBoxLayout()
        controls.addWidget(self.prev_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.counter)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas, 1)
        layout.addLayout(controls)
        self.retranslate(language)

    def retranslate(self, language: str) -> None:
        self.language = language
        self.prev_button.setText(tr(language, "previous"))
        self.play_button.setText(tr(language, "pause" if self.playing else "play"))
        self.next_button.setText(tr(language, "next"))
        if not self.clip:
            self.canvas.setText(tr(language, "drop"))

    def set_clip(self, clip: MediaClip | None) -> None:
        self.stop()
        self.clip = clip
        self.frame = 0
        maximum = max(0, (clip.total_frames - 1) if clip else 0)
        self.slider.blockSignals(True)
        self.slider.setRange(0, maximum)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self._update_counter()
        if clip:
            self.render()
        else:
            self.canvas.clear()
            self.canvas.setText(tr(self.language, "drop"))

    def _slider_changed(self, value: int) -> None:
        self.frame = value
        self._update_counter()
        self.render()

    def step(self, delta: int) -> None:
        if not self.clip:
            return
        self.stop()
        self.slider.setValue(max(0, min(self.slider.maximum(), self.frame + delta)))

    def toggle_play(self) -> None:
        if not self.clip:
            return
        if self.playing:
            self.stop()
            return
        self.playing = True
        self.play_button.setText(tr(self.language, "pause"))
        interval = max(8, round(1000 / max(1.0, self.clip.fps)))
        self.timer.start(interval)

    def stop(self) -> None:
        self.playing = False
        self.timer.stop()
        self.play_button.setText(tr(self.language, "play"))

    def _tick(self) -> None:
        if not self.clip or self.frame >= self.slider.maximum():
            self.stop()
            return
        self.slider.setValue(self.frame + 1)

    def _update_counter(self) -> None:
        total = self.clip.total_frames if self.clip else 0
        self.counter.setText(f"{min(total, self.frame + 1) if total else 0} / {total}")

    def render(self) -> None:
        clip = self.clip
        if not clip:
            return
        pixmap = QPixmap(clip.sequence_file_for_frame(self.frame)) if clip.media_type == "sequence" else self._video_frame(clip)
        if not pixmap.isNull():
            self.canvas.setPixmap(pixmap.scaled(self.canvas.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.clip:
            self.render()

    def _video_frame(self, clip: MediaClip) -> QPixmap:
        if not self.tools.ffmpeg:
            return QPixmap()
        seconds = self.frame / max(0.001, clip.fps)
        command = [self.tools.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-ss", f"{seconds:.9f}", "-i", str(Path(clip.path)), "-frames:v", "1", "-vf", "scale=960:540:force_original_aspect_ratio=decrease", "-f", "image2pipe", "-vcodec", "png", "pipe:1"]
        try:
            result = subprocess.run(command, capture_output=True, timeout=20, check=False, **hidden_subprocess_kwargs())
        except (OSError, subprocess.SubprocessError) as exc:
            self.message.emit(str(exc))
            return QPixmap()
        image = QImage.fromData(result.stdout, "PNG")
        return QPixmap.fromImage(image) if not image.isNull() else QPixmap()
