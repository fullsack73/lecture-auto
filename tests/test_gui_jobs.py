from threading import Event

import pytest

from lecture_auto.gui.jobs import JobController
from lecture_auto.tasking import TaskCancelledError


def test_mixed_jobs_run_in_request_order_including_same_session(qtbot) -> None:
    jobs = JobController()
    started, release = Event(), Event()
    order = []

    def transcribe(_token, _progress, _job):
        order.append('transcribe-1')
        started.set()
        assert release.wait(3)

    try:
        jobs.submit(transcribe, session_id='first')
        qtbot.waitUntil(started.is_set)
        for label, session in [('refine', 'first'), ('transcribe-2', 'second'), ('summarize', 'second')]:
            jobs.submit(lambda _t, _p, _j, label=label: order.append(label), session_id=session)
        assert jobs.active_count == 4
        assert jobs.pending_count == 3
        assert jobs.has_close_blocking_jobs
        assert order == ['transcribe-1']
    finally:
        release.set()
        qtbot.waitUntil(lambda: jobs.active_count == 0, timeout=3000)
    assert order == ['transcribe-1', 'refine', 'transcribe-2', 'summarize']


def test_audio_bypasses_ai_queue_and_does_not_hold_up_next_ai_job(qtbot) -> None:
    jobs = JobController()
    started, release = Event(), Event()
    audio_started, audio_release, next_ai = Event(), Event(), Event()

    def transcribe(_token, _progress, _job):
        started.set()
        assert release.wait(3)

    def audio(_token, _progress, _job):
        audio_started.set()
        assert audio_release.wait(3)

    try:
        jobs.submit(transcribe, session_id='lecture')
        qtbot.waitUntil(started.is_set)
        jobs.submit(lambda *_: next_ai.set(), session_id='lecture')
        # Even the same session's audio request must bypass pending AI work.
        jobs.submit(audio, session_id='lecture', queued=False)
        qtbot.waitUntil(audio_started.is_set)
        assert not next_ai.is_set()
        release.set()
        qtbot.waitUntil(next_ai.is_set)
        assert jobs.active_count >= 1
    finally:
        release.set()
        audio_release.set()
        qtbot.waitUntil(lambda: jobs.active_count == 0, timeout=3000)


@pytest.mark.parametrize('failure', [RuntimeError('provider failed'), TaskCancelledError('canceled')])
def test_failed_or_canceled_job_does_not_stop_queue(qtbot, failure) -> None:
    jobs = JobController()
    completed, failures = [], []
    jobs.failed.connect(lambda _job, error: failures.append(error))

    def fail(*_args):
        raise failure

    jobs.submit(fail, session_id='lecture')
    jobs.submit(lambda *_: completed.append('next'), session_id='lecture')
    qtbot.waitUntil(lambda: jobs.active_count == 0, timeout=3000)
    assert failures == [failure]
    assert completed == ['next']


def test_cancel_pending_job_removes_it_without_executing(qtbot) -> None:
    jobs = JobController()
    started, release = Event(), Event()
    completed, failures = [], []
    jobs.failed.connect(lambda job, error: failures.append((job, error)))

    def hold(*_args):
        started.set()
        assert release.wait(3)

    try:
        jobs.submit(hold)
        qtbot.waitUntil(started.is_set)
        canceled = jobs.submit(lambda *_: completed.append('canceled'))
        jobs.submit(lambda *_: completed.append('next'))
        jobs.cancel(canceled)
        assert jobs.active_count == 2
        assert failures[0][0] == canceled
        assert isinstance(failures[0][1], TaskCancelledError)
    finally:
        release.set()
        qtbot.waitUntil(lambda: jobs.active_count == 0, timeout=3000)
    assert completed == ['next']


def test_cancel_all_never_starts_waiting_work(qtbot) -> None:
    jobs = JobController()
    started, release = Event(), Event()
    executed = []

    def hold(*_args):
        started.set()
        assert release.wait(3)

    try:
        jobs.submit(hold)
        qtbot.waitUntil(started.is_set)
        jobs.submit(lambda *_: executed.append('refine'))
        jobs.submit(lambda *_: executed.append('summary'))
        jobs.cancel_all()
        assert jobs.active_count == 1
    finally:
        release.set()
        qtbot.waitUntil(lambda: jobs.active_count == 0, timeout=3000)
    assert executed == []


def test_transcription_and_llm_have_independent_fifo_queues(qtbot) -> None:
    import threading
    jobs = JobController()
    stt_started = threading.Event()
    llm_started = threading.Event()
    release_stt = threading.Event()
    release_llm = threading.Event()
    order = []
    def stt(*_args):
        stt_started.set()
        release_stt.wait(10)
    def llm(*_args):
        llm_started.set()
        release_llm.wait(10)
        order.append('first')
    try:
        jobs.submit(stt, session_id='lecture', lane='stt')
        qtbot.waitUntil(stt_started.is_set, timeout=3000)
        jobs.submit(llm, session_id='other', lane='llm')
        qtbot.waitUntil(llm_started.is_set, timeout=3000)
        jobs.submit(lambda *_: order.append('second'), lane='llm')
        assert order == []
        release_llm.set()
        qtbot.waitUntil(lambda: order == ['first', 'second'], timeout=3000)
        assert not release_stt.is_set()
    finally:
        release_llm.set()
        release_stt.set()
        qtbot.waitUntil(lambda: jobs.active_count == 0, timeout=5000)
