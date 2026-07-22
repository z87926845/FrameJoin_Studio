from __future__ import annotations

import subprocess
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

    def cancel(self) -> None:
        self._cancelled = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except OSError:
                pass

    def run(self) -> None:
        try:
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
            for path in self.plan.temporary_files:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _run_command(self, command: list[str]) -> None:
        self.message.emit(" ".join(command[:8]) + " …")
        self._process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1, **hidden_subprocess_kwargs())
        assert self._process.stdout is not None
        duration = max(0.001, self.plan.total_duration)
        for line in self._process.stdout:
            if self._cancelled:
                break
            if line.startswith("out_time_ms="):
                try:
                    self.progress.emit(max(0.0, min(1.0, int(line.split("=", 1)[1]) / 1_000_000 / duration)))
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
