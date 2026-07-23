from __future__ import annotations

import subprocess
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QImage, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from .i18n import tr
from .models import MediaClip
from .tools import Toolchain, hidden_subprocess_kwargs

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    QT_MULTIMEDIA_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the packaged Qt build
    QAudioOutput = QMediaPlayer = QVideoWidget = None
    QT_MULTIMEDIA_AVAILABLE = False


class PreviewWidget(QWidget):
    """Ordered multi-clip preview that preserves each clip's real timing.

    Video clips use Qt Multimedia, which lets the operating-system backend use
    hardware decoding when available and fall back to software decoding when it
    is not. Image sequences use an elapsed-time clock, scaled-image cache and
    frame skipping so the timeline keeps real-time speed even when every frame
    cannot be painted.
    """

    message = Signal(str)

    def __init__(self, tools: Toolchain, language: str = "zh_CN", parent=None) -> None:
        super().__init__(parent)
        self.tools = tools
        self.language = language
        self.clips: list[MediaClip] = []
        self.selected_index = 0
        self.timeline: list[tuple[MediaClip, int, int, int]] = []
        self.position_ms = 0
        self.playing = False
        self._active_timeline_index = -1
        self._pending_video_seek = 0
        self._play_after_load = False
        self._dragging_slider = False
        self._sequence_frame_key: tuple[str, int] | None = None
        self._frame_cache: OrderedDict[tuple[str, int, int], QPixmap] = OrderedDict()

        self.clock = QElapsedTimer()
        self.play_base_ms = 0
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(5)
        self.timer.timeout.connect(self._tick)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("", "combined")
        self.mode_combo.addItem("", "selected")
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)

        self.decoder_status = QLabel()
        self.decoder_status.setObjectName("previewDecoderStatus")
        self.decoder_status.setWordWrap(True)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 2)
        top_row.addWidget(self.mode_combo)
        top_row.addStretch(1)
        top_row.addWidget(self.decoder_status)

        self.display_container = QWidget()
        self.display_stack = QStackedLayout(self.display_container)
        self.display_stack.setContentsMargins(0, 0, 0, 0)

        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumSize(480, 270)
        self.canvas.setStyleSheet(
            "background:#020813;border:1px solid #18456f;border-radius:10px;"
            "color:#7894ad;"
        )
        self.canvas.setScaledContents(False)
        self.display_stack.addWidget(self.canvas)

        self.player = None
        self.audio_output = None
        self.video_widget = None
        if QT_MULTIMEDIA_AVAILABLE:
            self.video_widget = QVideoWidget()
            self.video_widget.setMinimumSize(480, 270)
            self.video_widget.setStyleSheet("background:#020813;border-radius:10px;")
            self.display_stack.addWidget(self.video_widget)
            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.audio_output.setVolume(0.75)
            self.player.setAudioOutput(self.audio_output)
            self.player.setVideoOutput(self.video_widget)
            self.player.positionChanged.connect(self._video_position_changed)
            self.player.mediaStatusChanged.connect(self._video_status_changed)
            self.player.errorOccurred.connect(self._video_error)

        self.prev_button = QPushButton()
        self.play_button = QPushButton()
        self.next_button = QPushButton()
        self.prev_button.clicked.connect(lambda: self.step(-1))
        self.play_button.clicked.connect(self.toggle_play)
        self.next_button.clicked.connect(lambda: self.step(1))

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderPressed.connect(self._slider_pressed)
        self.slider.sliderReleased.connect(self._slider_released)
        self.slider.sliderMoved.connect(self._slider_moved)

        self.counter = QLabel("00:00.000 / 00:00.000")
        self.counter.setMinimumWidth(170)
        self.counter.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 2, 0, 0)
        controls.addWidget(self.prev_button)
        controls.addWidget(self.play_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.counter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(top_row)
        layout.addWidget(self.display_container, 1)
        layout.addLayout(controls)
        self.retranslate(language)

    def retranslate(self, language: str) -> None:
        self.language = language
        self.prev_button.setText(tr(language, "previous"))
        self.play_button.setText(tr(language, "pause" if self.playing else "play"))
        self.next_button.setText(tr(language, "next"))
        self.mode_combo.setItemText(0, tr(language, "preview_combined"))
        self.mode_combo.setItemText(1, tr(language, "preview_selected"))
        self._update_decoder_status()
        if not self.clips:
            self.canvas.setText(tr(language, "drop"))

    def set_clips(
        self,
        clips: list[MediaClip],
        selected_index: int = 0,
        *,
        jump_to_selection: bool = False,
    ) -> None:
        old_ids = [clip.clip_id for clip in self.clips]
        new_ids = [clip.clip_id for clip in clips]
        changed = old_ids != new_ids
        self.clips = list(clips)
        self.selected_index = max(0, min(int(selected_index), max(0, len(self.clips) - 1)))
        if changed:
            self.stop()
            self._frame_cache.clear()
            self._rebuild_timeline(jump_to_selection=jump_to_selection)
        elif self.mode_combo.currentData() == "selected":
            self._rebuild_timeline(jump_to_selection=True)
        elif jump_to_selection:
            self.jump_to_selected()
        self._update_decoder_status()

    def set_clip(self, clip: MediaClip | None) -> None:
        """Compatibility wrapper for older callers."""
        self.set_clips([clip] if clip else [], 0)

    def set_selected_index(self, index: int, *, jump: bool = True) -> None:
        if not self.clips:
            return
        self.selected_index = max(0, min(int(index), len(self.clips) - 1))
        if self.mode_combo.currentData() == "selected":
            self._rebuild_timeline(jump_to_selection=True)
        elif jump:
            self.jump_to_selected()

    def jump_to_selected(self) -> None:
        for _clip, source_index, start_ms, _end_ms in self.timeline:
            if source_index == self.selected_index:
                self.seek_ms(start_ms)
                return

    def _mode_changed(self, _index: int) -> None:
        self._rebuild_timeline(jump_to_selection=True)

    def _displayed_clips(self) -> list[tuple[MediaClip, int]]:
        if not self.clips:
            return []
        if self.mode_combo.currentData() == "selected":
            return [(self.clips[self.selected_index], self.selected_index)]
        return list(zip(self.clips, range(len(self.clips))))

    @staticmethod
    def _clip_duration_ms(clip: MediaClip) -> int:
        duration = float(clip.duration or 0.0)
        if duration <= 0 and clip.total_frames > 0 and clip.fps > 0:
            duration = clip.total_frames / clip.fps
        return max(1, round(duration * 1000))

    def _rebuild_timeline(self, *, jump_to_selection: bool = False) -> None:
        self.stop()
        self.timeline.clear()
        cursor = 0
        for clip, source_index in self._displayed_clips():
            end = cursor + self._clip_duration_ms(clip)
            self.timeline.append((clip, source_index, cursor, end))
            cursor = end
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, cursor))
        self.slider.blockSignals(False)
        target = 0
        if jump_to_selection and self.mode_combo.currentData() == "combined":
            for _clip, source_index, start, _end in self.timeline:
                if source_index == self.selected_index:
                    target = start
                    break
        self.seek_ms(target)

    def _locate(self, position_ms: int) -> tuple[int, MediaClip, int, int, int] | None:
        if not self.timeline:
            return None
        position_ms = max(0, min(position_ms, self.timeline[-1][3]))
        for index, (clip, source_index, start, end) in enumerate(self.timeline):
            if position_ms < end or index == len(self.timeline) - 1:
                return index, clip, source_index, start, max(0, position_ms - start)
        return None

    def _slider_pressed(self) -> None:
        self._dragging_slider = True

    def _slider_moved(self, value: int) -> None:
        self.position_ms = int(value)
        self._update_counter()
        if not self.playing:
            self.seek_ms(value)

    def _slider_released(self) -> None:
        self._dragging_slider = False
        self.seek_ms(self.slider.value())
        if self.playing and self._current_clip_type() == "sequence":
            self.play_base_ms = self.position_ms
            self.clock.restart()

    def seek_ms(self, position_ms: int) -> None:
        located = self._locate(int(position_ms))
        if not located:
            self.position_ms = 0
            self._set_slider_value(0)
            self.canvas.clear()
            self.canvas.setText(tr(self.language, "drop"))
            self.display_stack.setCurrentWidget(self.canvas)
            self._update_counter()
            return
        timeline_index, clip, _source_index, _start, local_ms = located
        self.position_ms = max(0, min(int(position_ms), self.slider.maximum()))
        self._set_slider_value(self.position_ms)
        self._active_timeline_index = timeline_index
        if clip.media_type == "video" and self.player and self.video_widget:
            self.display_stack.setCurrentWidget(self.video_widget)
            self._load_video(timeline_index, clip, local_ms)
        else:
            self.display_stack.setCurrentWidget(self.canvas)
            if clip.media_type == "sequence":
                frame = min(max(0, clip.total_frames - 1), int((local_ms / 1000.0) * max(0.001, clip.fps)))
                self._render_sequence_frame(clip, frame)
            else:
                frame = int((local_ms / 1000.0) * max(0.001, clip.fps))
                self._render_video_fallback(clip, frame)
        self._update_counter()
        self._update_decoder_status()

    def _set_slider_value(self, value: int) -> None:
        if self._dragging_slider:
            return
        self.slider.blockSignals(True)
        self.slider.setValue(int(value))
        self.slider.blockSignals(False)

    def toggle_play(self) -> None:
        if not self.timeline:
            return
        if self.playing:
            self.stop()
            return
        if self.position_ms >= self.slider.maximum():
            self.seek_ms(0)
        self.playing = True
        self.play_button.setText(tr(self.language, "pause"))
        if self._current_clip_type() == "video" and self.player:
            self._play_after_load = True
            self.player.play()
            self.timer.start(30)
        else:
            self.play_base_ms = self.position_ms
            self.clock.restart()
            self.timer.start()

    def stop(self) -> None:
        self.playing = False
        self._play_after_load = False
        self.timer.stop()
        if self.player:
            self.player.pause()
        self.play_button.setText(tr(self.language, "play"))

    def step(self, delta: int) -> None:
        located = self._locate(self.position_ms)
        if not located:
            return
        self.stop()
        _index, clip, _source_index, _start, _local_ms = located
        step_ms = max(1, round(1000 / max(0.001, clip.fps)))
        self.seek_ms(self.position_ms + (step_ms * int(delta)))

    def _tick(self) -> None:
        if not self.playing or not self.timeline:
            return
        if self._current_clip_type() == "video" and self.player:
            # QMediaPlayer supplies timestamp-accurate video positions. This timer
            # only keeps the combined timeline responsive between its signals.
            located = self._locate(self.position_ms)
            if located:
                index, _clip, _source_index, start, _local = located
                if index == self._active_timeline_index:
                    self.position_ms = start + int(self.player.position())
                    self._set_slider_value(self.position_ms)
                    self._update_counter()
            return
        target = self.play_base_ms + self.clock.elapsed()
        if target >= self.slider.maximum():
            self.seek_ms(self.slider.maximum())
            self.stop()
            return
        self.seek_ms(target)

    def _current_clip_type(self) -> str:
        located = self._locate(self.position_ms)
        return located[1].media_type if located else ""

    def _load_video(self, timeline_index: int, clip: MediaClip, local_ms: int) -> None:
        if not self.player:
            return
        source = QUrl.fromLocalFile(str(Path(clip.path).resolve()))
        if self.player.source() != source:
            self._pending_video_seek = int(local_ms)
            self._play_after_load = self.playing
            self.player.setSource(source)
        else:
            if abs(int(self.player.position()) - int(local_ms)) > 35:
                self.player.setPosition(int(local_ms))
            if self.playing:
                self.player.play()
        self._active_timeline_index = timeline_index

    def _video_status_changed(self, status) -> None:
        if not self.player or not QT_MULTIMEDIA_AVAILABLE:
            return
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            self.player.setPosition(max(0, int(self._pending_video_seek)))
            if self._play_after_load:
                self.player.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._advance_video_segment()

    def _advance_video_segment(self) -> None:
        next_index = self._active_timeline_index + 1
        if next_index >= len(self.timeline):
            self.seek_ms(self.slider.maximum())
            self.stop()
            return
        _clip, _source_index, start, _end = self.timeline[next_index]
        self.seek_ms(start)
        if self.playing and self.player:
            self._play_after_load = True
            self.player.play()

    def _video_position_changed(self, local_ms: int) -> None:
        if self._active_timeline_index < 0 or self._active_timeline_index >= len(self.timeline):
            return
        _clip, _source_index, start, _end = self.timeline[self._active_timeline_index]
        self.position_ms = min(self.slider.maximum(), start + int(local_ms))
        self._set_slider_value(self.position_ms)
        self._update_counter()

    def _video_error(self, *_args) -> None:
        if self.player:
            detail = self.player.errorString() or tr(self.language, "preview_decode_failed")
            self.message.emit(detail)

    def _render_sequence_frame(self, clip: MediaClip, frame: int) -> None:
        path = clip.sequence_file_for_frame(frame)
        width = max(1, self.canvas.width())
        height = max(1, self.canvas.height())
        cache_key = (path, width, height)
        pixmap = self._frame_cache.get(cache_key)
        if pixmap is None:
            reader = QImageReader(path)
            reader.setAutoTransform(True)
            original = reader.size()
            if original.isValid() and (original.width() > width or original.height() > height):
                original.scale(QSize(width, height), Qt.AspectRatioMode.KeepAspectRatio)
                reader.setScaledSize(original)
            image = reader.read()
            pixmap = QPixmap.fromImage(image) if not image.isNull() else QPixmap()
            if not pixmap.isNull():
                self._frame_cache[cache_key] = pixmap
                self._frame_cache.move_to_end(cache_key)
                while len(self._frame_cache) > 32:
                    self._frame_cache.popitem(last=False)
        if not pixmap.isNull():
            self.canvas.setPixmap(
                pixmap.scaled(
                    self.canvas.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._sequence_frame_key = (clip.clip_id, frame)

    def _render_video_fallback(self, clip: MediaClip, frame: int) -> None:
        if not self.tools.ffmpeg:
            return
        seconds = frame / max(0.001, clip.fps)
        base = [
            self.tools.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
        ]
        tail = [
            "-ss",
            f"{seconds:.9f}",
            "-i",
            str(Path(clip.path)),
            "-frames:v",
            "1",
            "-vf",
            "scale=960:540:force_original_aspect_ratio=decrease",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ]
        for command in (base + ["-hwaccel", "auto"] + tail, base + tail):
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    timeout=20,
                    check=False,
                    **hidden_subprocess_kwargs(),
                )
            except (OSError, subprocess.SubprocessError) as exc:
                self.message.emit(str(exc))
                return
            image = QImage.fromData(result.stdout, "PNG")
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                self.canvas.setPixmap(
                    pixmap.scaled(
                        self.canvas.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return

    def _update_decoder_status(self) -> None:
        clip_type = self._current_clip_type()
        if clip_type == "video":
            key = "preview_video_hw" if self.player else "preview_video_fallback"
        elif clip_type == "sequence":
            key = "preview_sequence_clock"
        else:
            key = "preview_ready"
        self.decoder_status.setText(tr(self.language, key))

    @staticmethod
    def _format_ms(value: int) -> str:
        value = max(0, int(value))
        minutes, remainder = divmod(value, 60_000)
        seconds, milliseconds = divmod(remainder, 1000)
        return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def _update_counter(self) -> None:
        total = self.slider.maximum()
        self.counter.setText(f"{self._format_ms(self.position_ms)} / {self._format_ms(total)}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        located = self._locate(self.position_ms)
        if located and located[1].media_type == "sequence":
            self._frame_cache.clear()
            self.seek_ms(self.position_ms)
