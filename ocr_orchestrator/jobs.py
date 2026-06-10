"""In-memory async job store.

v1 limitation (documented in the spec): single uvicorn worker only and jobs
are lost on restart — there is no persistence. An ``asyncio.Lock`` serialises
mutations; ``OrderedDict`` + ``retention`` bounds memory growth.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from .models import ApplicationResult, JobStage, JobState, StageState

_DEFAULT_STAGES = ("classify", "extract", "verify", "aggregate")


@dataclass
class Job:
    id: str
    status: JobState = "pending"
    stages: list[JobStage] = field(default_factory=list)
    result: Optional[ApplicationResult] = None
    error: Optional[str] = None
    # Kept so the background task isn't garbage-collected mid-run. Never serialised.
    task: Optional[asyncio.Task] = None


class JobStore:
    def __init__(self, retention: int = 200) -> None:
        self._jobs: "OrderedDict[str, Job]" = OrderedDict()
        self._lock = asyncio.Lock()
        self._retention = max(1, retention)

    async def create(self) -> Job:
        async with self._lock:
            job = Job(
                id=uuid.uuid4().hex,
                stages=[JobStage(name=n) for n in _DEFAULT_STAGES],
            )
            self._jobs[job.id] = job
            while len(self._jobs) > self._retention:
                self._jobs.popitem(last=False)  # evict oldest
            return job

    async def get(self, job_id: str) -> Optional[Job]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def set_status(self, job_id: str, status: JobState) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = status

    async def set_stage(
        self, job_id: str, name: str, status: StageState,
        error: Optional[str] = None,
    ) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for stage in job.stages:
                if stage.name == name:
                    stage.status = status
                    stage.error = error
                    break

    async def set_result(self, job_id: str, result: ApplicationResult) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.result = result
                job.status = "completed"

    async def fail(self, job_id: str, error: str) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.error = error
                job.status = "failed"

    async def attach_task(self, job_id: str, task: asyncio.Task) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.task = task
