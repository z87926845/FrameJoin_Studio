from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QListWidget

from .exporter import ExportPlan
from .probe import is_image_path, is_video_path
from .tools import hidden_subprocess_kwargs


class DropListWidget(QListWidget):
    paths_dropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event) -> None:
        event.acceptProposedAction() if event.mimeData().hasUrls() else super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction() if event.mimeData().hasUrls() else super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            supported = [path for path in paths if is_video_path(path) or is_image_path(path)]
            if supported:
                self.paths_dropped.emit(supported)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class ExportThread(QThread):
    progress = Signal(float)
    message = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, plan: ExportPlan, output_path: str, parent=None) -> None:
        super().__init__(parent)
        self.plan = plan
        self.output_path = output_path
        self._process: subprocess.Popen | None = None
        self._cancelled = False
        self._staging_directory: Path | None = None

    def cancel(self) -> None:
        self._cancelled = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except OSError:
                pass

    def run(self) -> None:
        try:
            if self.plan.file_copies:
                self._run_file_copies()
            for command in self.plan.commands:
                if self._cancelled:
                    raise RuntimeError("cancelled")
                self._run_command(command)
            if not self._cancelled:
                self.progress.emit(1.0)
                self.succeeded.emit(self.output_path)
        except Exception as exc:
            self.failed.emit("cancelled" if self._cancelled else str(exc))
        finally:
            self._process = None
            if self._staging_directory and self._staging_directory.exists():
                shutil.rmtree(self._staging_directory, ignore_errors=True)
            self._staging_directory = None
            for path in self.plan.temporary_files:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _run_file_copies(self) -> None:
        target = self.plan.output_directory
        if target is None:
            raise RuntimeError("连续序列帧输出缺少目标目录。")
        target = target.resolve()
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            raise RuntimeError("连续序列帧输出目录必须不存在或为空目录。")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.parent / f".{target.name}.framejoin-{uuid4().hex}"
        staging.mkdir(parents=False, exist_ok=False)
        self._staging_directory = staging

        total = max(1, len(self.plan.file_copies))
        for index, (source, filename) in enumerate(self.plan.file_copies, start=1):
            if self._cancelled:
                raise RuntimeError("cancelled")
            destination = staging / filename
            self.message.emit(f"{source.name} → {filename}")
            shutil.copy2(source, destination)
            self.progress.emit(index / total)

        if target.exists():
            target.rmdir()
        os.replace(staging, target)
        self._staging_directory = None

    def _run_command(self, command: list[str]) -> None:
        self.message.emit(" ".join(command[:8]) + " …")
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **hidden_subprocess_kwargs(),
        )
        assert self._process.stdout is not None
        duration = max(0.001, self.plan.total_duration)
        for line in self._process.stdout:
            if self._cancelled:
                break
            if line.startswith("out_time_ms="):
                try:
                    self.progress.emit(
                        max(0.0, min(1.0, int(line.split("=", 1)[1]) / 1_000_000 / duration))
                    )
                except ValueError:
                    pass
        stderr = self._process.stderr.read() if self._process.stderr else ""
        code = self._process.wait()
        if not self._cancelled and code != 0:
            detail = stderr.strip().splitlines()
            raise RuntimeError(detail[-1] if detail else f"FFmpeg exited with code {code}")


def format_bytes(value: int) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
