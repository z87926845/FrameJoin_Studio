from __future__ import annotations

import traceback
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class FunctionWorker(QRunnable):
    def __init__(self, function: Callable, *args, **kwargs) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced to GUI
            detail = f"{exc}\n\n{traceback.format_exc()}"
            self.signals.error.emit(detail)
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
