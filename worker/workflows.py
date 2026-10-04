"""
worker/workflows.py — IngestWorkflow
Orchestrates: hash_and_check → parse → chunk → embed → upsert → tag_topic → pregen_questions
Each step is retryable independently. Kill the worker mid-run → Temporal replays from last completed activity.
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from worker.activities import (
        hash_and_check,
        parse_activity,
        chunk_activity,
        embed_activity,
        upsert_activity,
        tag_topic_activity,
        pregen_questions_activity,
    )


@workflow.defn
class IngestWorkflow:
    @workflow.run
    async def run(self, path: str) -> dict:
        # ── Activity 1: Hash + dedup check ───────────────────────────────────
        check_result = await workflow.execute_activity(
            hash_and_check,
            path,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        if check_result["status"] == "skipped":
            return {"status": "skipped", "doc_id": check_result["doc_id"]}

        doc_id = check_result["doc_id"]

        # ── Activity 2: Parse ─────────────────────────────────────────────────
        parse_result = await workflow.execute_activity(
            parse_activity,
            {"path": path, "doc_id": doc_id},
            start_to_close_timeout=timedelta(minutes=5),  # OCR can be slow
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        # ── Activity 3: Chunk ─────────────────────────────────────────────────
        chunk_result = await workflow.execute_activity(
            chunk_activity,
            {"pages": parse_result["pages"]},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # ── Activity 4: Embed ─────────────────────────────────────────────────
        embed_result = await workflow.execute_activity(
            embed_activity,
            {"chunks": chunk_result["chunks"]},
            start_to_close_timeout=timedelta(minutes=10),  # Ollama on CPU is slow
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=5),
                maximum_interval=timedelta(seconds=30),
            ),
        )

        # ── Activity 5: Upsert to DB ──────────────────────────────────────────
        upsert_result = await workflow.execute_activity(
            upsert_activity,
            {
                "doc_id": doc_id,
                "chunks": chunk_result["chunks"],
                "vectors": embed_result["vectors"],
            },
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )

        # ── Activity 6: Tag topics (no-op Day 1) ─────────────────────────────
        await workflow.execute_activity(
            tag_topic_activity,
            {"doc_id": doc_id},
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        # ── Activity 7: Pre-gen questions (no-op Day 1) ───────────────────────
        await workflow.execute_activity(
            pregen_questions_activity,
            {"doc_id": doc_id},
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        return {
            "status": "done",
            "doc_id": doc_id,
            "chunk_count": upsert_result["chunk_count"],
        }
