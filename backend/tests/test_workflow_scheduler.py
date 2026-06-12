"""WorkflowScheduler failure backoff.

The scheduler must keep running when a cycle fails, but back off exponentially
(capped) while failures persist and recover to the normal interval on success.
These tests drive the synchronous cycle path with a stubbed runner and an
in-memory session scope, so no event loop or live DB is required.
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from app.workflow.scheduler import WorkflowScheduler


class _Runner:
    def __init__(self) -> None:
        self.mode = "ok"
        self.calls = 0

    def run_once(self, session) -> dict:
        self.calls += 1
        if self.mode == "fail":
            raise RuntimeError("boom")
        if self.mode == "partial":
            return {"errors": ["quote sync failed"]}
        return {"ok": True}


@pytest.fixture
def patched_scope(monkeypatch):
    @contextlib.contextmanager
    def _scope():
        yield None

    monkeypatch.setattr("app.workflow.scheduler.session_scope", _scope)


def _scheduler(interval=10, max_backoff=100) -> tuple[WorkflowScheduler, _Runner]:
    runner = _Runner()
    return WorkflowScheduler(runner, interval, max_backoff_seconds=max_backoff), runner


def test_next_delay_is_interval_when_healthy():
    sch, _ = _scheduler(interval=10, max_backoff=100)
    assert sch._next_delay() == 10


def test_next_delay_backs_off_exponentially_and_caps():
    sch, _ = _scheduler(interval=10, max_backoff=100)
    expected = {0: 10, 1: 10, 2: 20, 3: 40, 4: 80, 5: 100, 6: 100}
    for failures, delay in expected.items():
        sch.consecutive_failures = failures
        assert sch._next_delay() == delay


def test_max_backoff_never_below_interval():
    sch, _ = _scheduler(interval=60, max_backoff=10)  # nonsensical cap
    assert sch.max_backoff == 60


def test_cycle_failure_increments_and_success_resets(patched_scope):
    sch, runner = _scheduler(interval=10, max_backoff=100)

    runner.mode = "fail"
    sch._run_cycle()
    assert sch.consecutive_failures == 1
    assert sch._next_delay() == 10
    assert sch.last_error == "boom"

    sch._run_cycle()
    assert sch.consecutive_failures == 2
    assert sch._next_delay() == 20

    runner.mode = "ok"
    sch._run_cycle()
    assert sch.consecutive_failures == 0
    assert sch.last_error is None
    assert sch._next_delay() == 10


def test_status_exposes_backoff_fields(patched_scope):
    sch, runner = _scheduler(interval=10, max_backoff=100)
    runner.mode = "fail"
    sch._run_cycle()
    status = sch.status()
    assert status["consecutive_failures"] == 1
    assert status["next_delay_seconds"] == 10


def test_partial_cycle_errors_trigger_backoff(patched_scope):
    sch, runner = _scheduler(interval=10, max_backoff=100)
    runner.mode = "partial"

    summary = sch._run_cycle()

    assert summary["errors"] == ["quote sync failed"]
    assert sch.consecutive_failures == 1
    assert sch.last_error == "quote sync failed"


def test_stop_resets_failure_streak():
    sch, _ = _scheduler()
    sch.consecutive_failures = 3
    sch.stop()
    assert sch.consecutive_failures == 0


def test_periodic_loop_offloads_sync_cycle_from_event_loop(
    patched_scope,
    monkeypatch,
):
    sch, runner = _scheduler(interval=10, max_backoff=100)
    offloaded = 0

    async def fake_to_thread(function):
        nonlocal offloaded
        offloaded += 1
        result = function()
        sch.running = False
        return result

    monkeypatch.setattr("app.workflow.scheduler.asyncio.to_thread", fake_to_thread)
    sch.running = True

    asyncio.run(sch._loop())

    assert offloaded == 1
    assert runner.calls == 1
