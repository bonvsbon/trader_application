"""Interval scheduler (Phase 1: status + countdown + manual trigger).

Holds the running/last/next/countdown state the UI displays. The periodic loop
is opt-in (started via the API, off by default) and only runs the read-only
`WorkflowRunner` cycle. Full auto-execution scheduling is Phase 3.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.logging import get_logger
from app.persistence.db import session_scope
from app.workflow.runner import WorkflowRunner

logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowScheduler:
    def __init__(
        self,
        runner: WorkflowRunner,
        interval_seconds: int,
        max_backoff_seconds: int | None = None,
    ) -> None:
        self.runner = runner
        self.interval = interval_seconds
        # Ceiling for failure backoff; never shorter than the normal interval.
        self.max_backoff = max(interval_seconds, max_backoff_seconds or interval_seconds)
        self.running = False
        self.current_step = "idle"
        self.last_run: datetime | None = None
        self.next_run: datetime | None = None
        self.last_error: str | None = None
        self.consecutive_failures = 0
        self._task: asyncio.Task | None = None

    def _next_delay(self) -> int:
        """Seconds until the next cycle: the interval, or an exponential backoff
        (capped) while cycles keep failing."""
        if self.consecutive_failures <= 0:
            return self.interval
        # Cap the exponent so the shift can't overflow on a long outage.
        factor = 2 ** min(self.consecutive_failures - 1, 20)
        return min(self.max_backoff, self.interval * factor)

    def status(self) -> dict:
        countdown = None
        if self.running and self.next_run is not None:
            countdown = max(0, int((self.next_run - _now()).total_seconds()))
        return {
            "running": self.running,
            "current_step": self.current_step,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "countdown_seconds": countdown,
            "interval_seconds": self.interval,
            "next_delay_seconds": self._next_delay(),
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
        }

    def start(self) -> dict:
        if not self.running:
            self.running = True
            self.consecutive_failures = 0
            self.next_run = _now() + timedelta(seconds=self.interval)
            self._task = asyncio.create_task(self._loop())
            logger.info("Workflow scheduler started (interval=%ss)", self.interval)
        return self.status()

    def stop(self) -> dict:
        self.running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self.current_step = "idle"
        self.next_run = None
        self.consecutive_failures = 0
        logger.info("Workflow scheduler stopped")
        return self.status()

    def run_once_now(self) -> dict:
        """Manual trigger — runs a single cycle synchronously."""
        summary = self._run_cycle()
        if self.running:
            self.next_run = _now() + timedelta(seconds=self._next_delay())
        return summary

    def _run_cycle(self) -> dict:
        self.current_step = "running"
        try:
            with session_scope() as session:
                summary = self.runner.run_once(session)
            self.last_run = _now()
            errors = summary.get("errors") or []
            if errors:
                self.consecutive_failures += 1
                self.last_error = "; ".join(str(error) for error in errors)
                logger.warning(
                    "Workflow cycle completed with errors (%d in a row); backing off to %ss",
                    self.consecutive_failures,
                    self._next_delay(),
                )
            else:
                self.last_error = None
                self.consecutive_failures = 0
            return summary
        except Exception as exc:
            self.consecutive_failures += 1
            self.last_error = str(exc)
            logger.warning(
                "Workflow cycle failed (%d in a row); backing off to %ss",
                self.consecutive_failures,
                self._next_delay(),
            )
            return {"error": str(exc)}
        finally:
            self.current_step = "idle"

    async def _loop(self) -> None:
        try:
            while self.running:
                await asyncio.to_thread(self._run_cycle)
                delay = self._next_delay()
                self.next_run = _now() + timedelta(seconds=delay)
                # Sleep in 1s steps so stop() is responsive.
                for _ in range(delay):
                    if not self.running:
                        break
                    await asyncio.sleep(1)
        except asyncio.CancelledError:  # normal on stop()
            pass


_scheduler: WorkflowScheduler | None = None


def get_scheduler() -> WorkflowScheduler:
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = WorkflowScheduler(
            WorkflowRunner(settings=settings),
            settings.workflow_interval_seconds,
            max_backoff_seconds=settings.workflow_max_backoff_seconds,
        )
    return _scheduler


def reset_scheduler() -> None:
    """Stop and discard the scheduler so it picks up a replaced MT5 bridge."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.stop()
        _scheduler = None
