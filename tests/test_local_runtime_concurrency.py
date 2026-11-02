from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from lecture_auto.local_runtime import LocalRuntimeError, LocalRuntimeManager
from lecture_auto.tasking import CancellationToken, TaskCancelledError


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    script = tmp_path / "worker.py"
    script.write_text(
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "count = 0\n"
        "for line in sys.stdin:\n"
        " request = json.loads(line)\n"
        " count += 1\n"
        " print(json.dumps({'type': 'progress', 'stage': 'running'}), flush=True)\n"
        " deadline = time.monotonic() + 5\n"
        " while request.get('gate') and not Path(request['gate']).exists():\n"
        "  if time.monotonic() > deadline: raise RuntimeError('test gate timed out')\n"
        "  time.sleep(.01)\n"
        " if request.get('fail'):\n"
        "  print(json.dumps({'type': 'error', 'message': 'test failure'}), flush=True)\n"
        " elif request.get('crash'):\n"
        "  sys.exit(7)\n"
        " else:\n"
        "  print(json.dumps({'type': 'result', 'result': {'pid': os.getpid(), 'count': count}}), flush=True)\n",
        encoding="utf-8",
    )
    manager = LocalRuntimeManager(tmp_path / "runtime", worker_script=script)
    monkeypatch.setattr(manager, "python_for", lambda _feature: Path(sys.executable))
    yield manager
    manager.close()


@pytest.mark.parametrize("expired", [False, True])
def test_concurrent_transcriptions_are_isolated_and_reuse_warm_model(
    runtime: LocalRuntimeManager, tmp_path: Path, expired: bool
) -> None:
    started = Event()
    gate = tmp_path / "release"
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            runtime.run_feature, "whisper", {"gate": str(gate)},
            progress=lambda *_: started.set(), timeout=4,
        )
        try:
            assert started.wait(2)
            warm = next(iter(runtime._warm_workers.values()))
            if expired:
                warm.last_used -= 600
            second = executor.submit(runtime.run_feature, "whisper", {}, timeout=4)
            second_result = second.result(timeout=2)
            assert not first.done()
            assert warm.alive
        finally:
            gate.touch()
        first_result = first.result(timeout=2)

    assert first_result["pid"] != second_result["pid"]
    third = runtime.run_feature("whisper", {}, timeout=2)
    assert third == {"pid": first_result["pid"], "count": 2}


@pytest.mark.parametrize("failure", ["fail", "crash", "cancel", "timeout"])
def test_failed_transcription_does_not_stop_sibling_or_retry(
    runtime: LocalRuntimeManager, tmp_path: Path, failure: str
) -> None:
    started, sibling_started = Event(), Event()
    gate, sibling_gate = tmp_path / "release", tmp_path / "release-sibling"
    token = CancellationToken()
    request = {"gate": str(gate), failure: True}
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            runtime.run_feature, "whisper", request,
            progress=lambda *_: started.set(), cancellation_token=token,
            timeout=0.5 if failure == "timeout" else 4,
        )
        try:
            assert started.wait(2)
            sibling = executor.submit(
                runtime.run_feature, "whisper", {"gate": str(sibling_gate)},
                progress=lambda *_: sibling_started.set(), timeout=4,
            )
            assert sibling_started.wait(2)
            if failure == "cancel":
                token.cancel()
            elif failure != "timeout":
                gate.touch()
            expected = TaskCancelledError if failure == "cancel" else LocalRuntimeError
            with pytest.raises(expected):
                first.result(timeout=2)
            assert not sibling.done()
            retry = runtime.run_feature("whisper", {}, timeout=2)
            assert retry["count"] == 1
        finally:
            gate.touch()
            sibling_gate.touch()
        assert sibling.result(timeout=2)["pid"] != retry["pid"]


def test_cancelled_request_does_not_stop_busy_worker(
    runtime: LocalRuntimeManager, tmp_path: Path
) -> None:
    started = Event()
    gate = tmp_path / "release"
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(
            runtime.run_feature, "whisper", {"gate": str(gate)},
            progress=lambda *_: started.set(), timeout=4,
        )
        try:
            assert started.wait(2)
            token = CancellationToken()
            token.cancel()
            with pytest.raises(TaskCancelledError):
                runtime.run_feature("whisper", {}, cancellation_token=token)
        finally:
            gate.touch()
        assert first.result(timeout=2)["count"] == 1


@pytest.mark.parametrize("failure", ["fail", "crash", "cancel", "timeout"])
def test_parallel_failure_does_not_discard_busy_warm_worker(
    runtime: LocalRuntimeManager, tmp_path: Path, failure: str
) -> None:
    started, parallel_started = Event(), Event()
    gate, parallel_gate = tmp_path / "release", tmp_path / "release-parallel"
    token = CancellationToken()
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            runtime.run_feature, "whisper", {"gate": str(gate)},
            progress=lambda *_: started.set(), timeout=4,
        )
        try:
            assert started.wait(2)
            warm = next(iter(runtime._warm_workers.values()))
            parallel = executor.submit(
                runtime.run_feature, "whisper", {"gate": str(parallel_gate), failure: True},
                progress=lambda *_: parallel_started.set(), cancellation_token=token,
                timeout=0.5 if failure == "timeout" else 4,
            )
            assert parallel_started.wait(2)
            if failure == "cancel":
                token.cancel()
            elif failure != "timeout":
                parallel_gate.touch()
            expected = TaskCancelledError if failure == "cancel" else LocalRuntimeError
            with pytest.raises(expected):
                parallel.result(timeout=2)
            assert warm.alive
            assert not first.done()
            assert next(iter(runtime._warm_workers.values())) is warm
        finally:
            gate.touch()
            parallel_gate.touch()
        first_result = first.result(timeout=2)
    assert runtime.run_feature("whisper", {}, timeout=2)["pid"] == first_result["pid"]


def test_waiting_request_can_be_cancelled_without_stopping_active_work(
    runtime: LocalRuntimeManager, tmp_path: Path
) -> None:
    started = Event()
    gate = tmp_path / "release"
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            runtime.run_feature, "whisper", {"gate": str(gate)},
            progress=lambda *_: started.set(), timeout=4,
        )
        try:
            assert started.wait(2)
            warm = next(iter(runtime._warm_workers.values()))
            token = CancellationToken()
            waiting = executor.submit(
                warm.request, {}, progress=None, cancellation_token=token, timeout=2,
            )
            token.cancel()
            with pytest.raises(TaskCancelledError):
                waiting.result(timeout=1)
            assert warm.alive
        finally:
            gate.touch()
        assert first.result(timeout=2)["count"] == 1
