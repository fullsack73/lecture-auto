from __future__ import annotations

import uuid
from collections import deque
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from lecture_auto.tasking import CancellationToken, TaskCancelledError, TaskEvent


JobCallable = Callable[[CancellationToken, Callable[[TaskEvent], None], str], Any]


class WorkerSignals(QObject):
    progress = Signal(object)
    succeeded = Signal(str, object)
    failed = Signal(str, object)


class Worker(QRunnable):
    def __init__(self, job_id: str, work: JobCallable, token: CancellationToken) -> None:
        super().__init__()
        self.job_id = job_id
        self.work = work
        self.token = token
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.token.raise_if_cancelled()
            self.signals.progress.emit(TaskEvent(self.job_id, None, "starting", 0, None, "Starting task."))
            result = self.work(self.token, self.signals.progress.emit, self.job_id)
            self.token.raise_if_cancelled()
            self.signals.progress.emit(TaskEvent(self.job_id, None, "complete", 1, 1, "Task complete."))
        except BaseException as exc:
            self.signals.failed.emit(self.job_id, exc)
        else:
            self.signals.succeeded.emit(self.job_id, result)


class JobController(QObject):
    progress = Signal(object)
    succeeded = Signal(str, object)
    failed = Signal(str, object)
    active_changed = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.audio_pool = QThreadPool(self)
        self._tokens: dict[str, CancellationToken] = {}
        self._sessions: dict[str, str | None] = {}
        self._blocks_close: dict[str, bool] = {}
        self._workers: dict[str, Worker] = {}
        self._pending: deque[str] = deque()
        self._serial_jobs: set[str] = set()
        self._running_job: str | None = None

    @property
    def active_count(self) -> int:
        return len(self._tokens)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def has_close_blocking_jobs(self) -> bool:
        return any(self._blocks_close.values())

    def is_session_busy(self, session_id: str) -> bool:
        return session_id in self._sessions.values()

    def submit(
        self,
        work: JobCallable,
        *,
        session_id: str | None = None,
        block_close: bool = True,
        queued: bool = True,
    ) -> str:
        if session_id and any(
            sid == session_id and job_id not in self._serial_jobs
            for job_id, sid in self._sessions.items()
        ):
            raise RuntimeError(f"Session '{session_id}' already has an active task.")
        job_id = uuid.uuid4().hex
        token = CancellationToken()
        worker = Worker(job_id, work, token)
        worker.signals.progress.connect(self.progress)
        worker.signals.succeeded.connect(self._succeed)
        worker.signals.failed.connect(self._fail)
        self._tokens[job_id] = token
        self._sessions[job_id] = session_id
        self._blocks_close[job_id] = block_close
        self._workers[job_id] = worker
        if queued:
            self._serial_jobs.add(job_id)
            self._pending.append(job_id)
        if queued:
            self._start_next()
        else:
            self.audio_pool.start(worker)
        self.active_changed.emit(self.active_count)
        return job_id

    def _start_next(self) -> None:
        if self._running_job is None and self._pending:
            self._running_job = self._pending.popleft()
            self.pool.start(self._workers[self._running_job])

    def cancel(self, job_id: str) -> None:
        token = self._tokens.get(job_id)
        if token:
            token.cancel()
            if job_id in self._pending:
                self._pending.remove(job_id)
                self._fail(job_id, TaskCancelledError("Task was canceled."))

    def cancel_all(self) -> None:
        for token in self._tokens.values():
            token.cancel()
        pending = tuple(self._pending)
        self._pending.clear()
        for job_id in pending:
            self._fail(job_id, TaskCancelledError("Task was canceled."))

    @Slot(str, object)
    def _succeed(self, job_id: str, result: object) -> None:
        self._finish(job_id)
        self.succeeded.emit(job_id, result)

    @Slot(str, object)
    def _fail(self, job_id: str, error: object) -> None:
        self._finish(job_id)
        self.failed.emit(job_id, error)

    def _finish(self, job_id: str) -> None:
        self._tokens.pop(job_id, None)
        self._sessions.pop(job_id, None)
        self._blocks_close.pop(job_id, None)
        self._workers.pop(job_id, None)
        self._serial_jobs.discard(job_id)
        if self._running_job == job_id:
            self._running_job = None
        self._start_next()
        self.active_changed.emit(self.active_count)
