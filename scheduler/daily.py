"""Daily ingestion scheduler — Phase 7.

Runs the full ingestion pipeline (fetch → parse → chunk → embed → index)
at 10:00 AM IST every day using APScheduler.

Run locally:
    python -m scheduler.daily

In production the same job is also triggered by GitHub Actions
(.github/workflows/ingest.yml) so the Railway process does not need to
stay alive purely for scheduling.  Run this locally or on a long-lived
server if you want the in-process scheduler instead.

Exit: Ctrl+C to stop.  Scheduled job failures are logged but do not
crash the scheduler — the next scheduled run will retry automatically.
"""
from __future__ import annotations

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def run_ingestion() -> None:
    """Execute the full ingestion pipeline; log outcome."""
    logger.info("scheduler: starting daily ingestion run")
    try:
        from ingestion.run import main as ingestion_main
        rc = ingestion_main(skip_fetch=False)
        if rc == 0:
            logger.info("scheduler: ingestion completed successfully")
        else:
            logger.error("scheduler: ingestion failed with exit code %d", rc)
    except Exception:
        logger.exception("scheduler: unexpected error during ingestion")


def main() -> None:
    # app/config.py configures the root logger; import it to apply log level.
    from app.config import settings  # noqa: F401

    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        run_ingestion,
        trigger=CronTrigger(hour=10, minute=0, timezone="Asia/Kolkata"),
        id="daily_ingestion",
        name="Daily corpus refresh",
        misfire_grace_time=3600,  # run even if up to 1 hour late
        coalesce=True,            # skip duplicate runs if scheduler was paused
    )

    logger.info(
        "scheduler: daily ingestion scheduled at 10:00 AM IST — press Ctrl+C to stop"
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler: shutting down")
        sys.exit(0)


if __name__ == "__main__":
    main()
