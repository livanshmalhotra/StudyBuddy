"""
worker/worker.py — Temporal worker entrypoint
Run: python worker/worker.py  (from the project root)
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Ensure the project root (parent of this file's directory) is on sys.path so
# that `core.*` and `worker.*` are importable when the script is run directly
# (e.g. `python worker/worker.py`) rather than as a module.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import sentry_sdk
from temporalio.client import Client
from temporalio.worker import Worker

from core.config import settings
from worker.workflows import IngestWorkflow
from worker.activities import (
    hash_and_check,
    parse_activity,
    chunk_activity,
    embed_activity,
    upsert_activity,
    tag_topic_activity,
    pregen_questions_activity,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Sentry (no-op if DSN is blank) ───────────────────────────────────────────
if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=1.0)
    logger.info("Sentry initialized for worker")


async def main():
    logger.info(f"Connecting to Temporal at {settings.TEMPORAL_HOST} ...")
    client = await Client.connect(settings.TEMPORAL_HOST)

    worker = Worker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[IngestWorkflow],
        activities=[
            hash_and_check,
            parse_activity,
            chunk_activity,
            embed_activity,
            upsert_activity,
            tag_topic_activity,
            pregen_questions_activity,
        ],
    )

    logger.info(f"Worker started on task queue '{settings.TEMPORAL_TASK_QUEUE}'. Waiting for workflows...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
