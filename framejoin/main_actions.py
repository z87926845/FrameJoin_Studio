from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QListWidgetItem, QMessageBox

from .exporter import build_join_plan, choose_join_extension
from .i18n import tr
from .models import JoinSettings, MediaClip
from .probe import is_image_path, is_video_path, probe_image_sequence, probe_media
from .ui_helpers import ExportThread, format_bytes


class MainActionsMixin:
    clips: list[MediaClip]

    def ordered_clips(self) -> list[MediaClip]:
        return [
            self.media_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.media_list.count())
        ]

    def add_video_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr(self.language, "add_video"), "", f"{tr(self.language, 'video_filter')} (*)"
        )
        self.add_paths(paths)

    def add_sequence_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr(self.language, "add_sequence"), "", f"{tr(self.language, 'image_filter')} (*)"
        )
        self.add_paths(paths)

    def add_paths(self, paths: list[str]) -> None:
        video_paths = [path for path in paths if is_video_path(path)]
        image_paths = [path for path in paths if is_image_path(path)]
        if video_paths and image_paths:
            QMessageBox.warning(self, tr(self.language, "open_failed"), tr(self.language, "mixed"))
            return
        if self.media_list.count():
            existing = {clip.media_type for clip in self.ordered_clips()}
            incoming = "sequence" if image_paths else "video"
            if existing and incoming not in existing:
                QMessageBox.warning(self, tr(self.language, "open_failed"), tr(self.language, "mixed"))
                return
        fps = self.settings_panel.fps_value()
        if image_paths:
            fps, ok = QInputDialog.getText(
                self,
                tr(self.language, "sequence_fps_title"),
                tr(self.language, "sequence_fps_prompt"),
                text=fps,
            )
            if not ok:
                return
        self.status_label.setText(tr(self.language, "probing"))
        QApplication = __import__("PySide6.QtWidgets", fromlist=["QApplication"]).QApplication
        seen_patterns: set[str] = set()
        for path in video_paths + image_paths:
            QApplication.processEvents()
            try:
                clip = (
                    probe_media(path, self.tools.ffprobe)
                    if is_video_path(path)
                    else probe_image_sequence(path, self.tools.ffprobe, fps)
                )
                if clip.media_type == "sequence" and clip.sequence_pattern in seen_patterns:
                    continue
                seen_patterns.add(clip.sequence_pattern)
                self._append_clip(clip)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, tr(self.language, "open_failed"), f"{Path(path).name}\n\n{exc}")
        self.status_label.setText(tr(self.language, "status_ready"))
        self.refresh_mode()

    def _append_clip(self, clip: MediaClip) -> None:
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, clip)
        self.media_list.addItem(item)
        self._update_item(item)
        if self.media_list.count() == 1:
            self.media_list.setCurrentItem(item)

    def _update_item(self, item: QListWidgetItem) -> None:
        clip: MediaClip = item.data(Qt.ItemDataRole.UserRole)
        kind = (
            "Image Sequence"
            if self.language == "en_US" and clip.media_type == "sequence"
            else ("Video" if self.language == "en_US" else clip.type_label)
        )
        item.setText(
            f"{kind} · {clip.name}\n{clip.resolution} · {clip.fps_display} fps · {clip.total_frames:,} frames"
        )
        item.setToolTip(clip.path if clip.media_type == "video" else clip.sequence_pattern)

    def remove_selected(self) -> None:
        for item in self.media_list.selectedItems():
            self.media_list.takeItem(self.media_list.row(item))
        self.refresh_mode()

    def move_selected(self, delta: int) -> None:
        row = self.media_list.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.media_list.count():
            return
        item = self.media_list.takeItem(row)
        self.media_list.insertItem(target, item)
        self.media_list.setCurrentRow(target)

    def apply_fps(self, value: str) -> None:
        try:
            for clip in self.ordered_clips():
                if clip.media_type == "sequence":
                    clip.set_fps_value(value)
            self.settings_panel.set_fps_value(value)
            for index in range(self.media_list.count()):
                self._update_item(self.media_list.item(index))
            self.refresh_mode()
        except ValueError:
            QMessageBox.warning(
                self, tr(self.language, "sequence_fps_title"), tr(self.language, "invalid_fps")
            )

    def browse_output(self) -> None:
        clips = self.ordered_clips()
        video_mode = bool(clips and clips[0].media_type == "video")
        if self.settings_panel.output_is_directory():
            path = QFileDialog.getExistingDirectory(
                self,
                tr(self.language, "output_folder"),
                self.settings_panel.output_edit.text().strip() or "",
                QFileDialog.Option.ShowDirsOnly,
            )
            if path:
                self.settings_panel.output_edit.setText(path)
            return

        settings = self.settings_panel.settings(video_mode)
        extension = choose_join_extension(clips, settings) or "mkv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr(self.language, "output"),
            f"framejoin_output.{extension}",
            f"{tr(self.language, 'output_filter')} (*.{extension})",
        )
        if path:
            if not Path(path).suffix:
                path += f".{extension}"
            self.settings_panel.output_edit.setText(path)

    def start_export(self, force_cpu: bool = False) -> None:
        clips = self.ordered_clips()
        output = self.settings_panel.output_edit.text().strip()
        if not clips:
            QMessageBox.warning(self, tr(self.language, "failed"), tr(self.language, "need_media"))
            return
        if not output:
            QMessageBox.warning(self, tr(self.language, "failed"), tr(self.language, "need_output"))
            return
        video_mode = clips[0].media_type == "video"
        settings = self.settings_panel.settings(video_mode)
        if force_cpu:
            settings.sequence_encoder_backend = "cpu"
            settings.video_encoder_backend = "cpu"
        try:
            plan = build_join_plan(
                clips,
                settings,
                output,
                self.tools.ffmpeg,
                self.capabilities.usable_hardware_encoders,
            )
        except Exception as exc:
            QMessageBox.critical(self, tr(self.language, "failed"), str(exc))
            return
        if plan.estimated_bytes:
            self.settings_panel.estimate_label.setText(
                tr(self.language, "estimated", size=format_bytes(plan.estimated_bytes))
            )
        self._active_settings = settings
        self._active_video_mode = video_mode
        self._cpu_fallback_attempted = force_cpu
        self.export_thread = ExportThread(plan, output, self)
        self.export_thread.progress.connect(lambda p: self.progress.setValue(round(p * 1000)))
        self.export_thread.message.connect(self.status_label.setText)
        self.export_thread.succeeded.connect(self._export_succeeded)
        self.export_thread.failed.connect(self._export_failed)
        self.settings_panel.set_running(True)
        self.progress.setValue(0)
        self.status_label.setText(tr(self.language, "exporting"))
        self.export_thread.start()

    def cancel_export(self) -> None:
        if self.export_thread:
            self.export_thread.cancel()

    def _export_succeeded(self, path: str) -> None:
        self.settings_panel.set_running(False)
        self.progress.setValue(1000)
        self.status_label.setText(tr(self.language, "done"))
        QMessageBox.information(self, tr(self.language, "done"), path)

    def _export_failed(self, detail: str) -> None:
        self.settings_panel.set_running(False)
        settings = getattr(self, "_active_settings", JoinSettings())
        video_mode = bool(getattr(self, "_active_video_mode", False))
        hardware_requested = (
            video_mode
            and settings.video_transcode_enabled
            and settings.video_encoder_backend != "cpu"
        ) or (
            not video_mode
            and settings.sequence_bitrate_enabled
            and settings.sequence_encoder_backend != "cpu"
        )
        if detail != "cancelled" and hardware_requested and not self._cpu_fallback_attempted:
            self.status_label.setText("Hardware encoder failed; retrying with CPU…")
            self.start_export(force_cpu=True)
            return
        self.status_label.setText(tr(self.language, "cancelled" if detail == "cancelled" else "failed"))
        if detail != "cancelled":
            QMessageBox.critical(self, tr(self.language, "failed"), detail)

    def save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, tr(self.language, "save_project"), "", tr(self.language, "project_filter")
        )
        if not path:
            return
        if not path.lower().endswith(".fjproj"):
            path += ".fjproj"
        clips = self.ordered_clips()
        video_mode = bool(clips and clips[0].media_type == "video")
        data = {
            "version": 2,
            "clips": [clip.to_dict() for clip in clips],
            "settings": self.settings_panel.settings(video_mode).to_dict(),
            "output": self.settings_panel.output_edit.text(),
            "fps": self.settings_panel.fps_value(),
        }
        try:
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status_label.setText(tr(self.language, "project_saved"))
        except OSError as exc:
            QMessageBox.critical(self, tr(self.language, "project_error"), str(exc))

    def load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr(self.language, "load_project"), "", tr(self.language, "project_filter")
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.media_list.clear()
            for raw in data.get("clips", []):
                self._append_clip(MediaClip.from_dict(raw))
            self.settings_panel.load_settings(JoinSettings.from_dict(data.get("settings", {})))
            self.settings_panel.output_edit.setText(data.get("output", ""))
            self.settings_panel.set_fps_value(data.get("fps", "24"))
            self.status_label.setText(tr(self.language, "project_loaded"))
            self.refresh_mode()
        except Exception as exc:
            QMessageBox.critical(self, tr(self.language, "project_error"), str(exc))
