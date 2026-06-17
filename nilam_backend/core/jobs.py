"""In-memory async job store (single worker), ported in spirit from
ocr_orchestrator. Holds one job per application: its emitted orchestration
events, the assembled ApplicationView, survey state, and enough raw context to
recompute the offer when an RM survey overrides NPW. Not durable (design §10).
"""

from typing import Any, Dict, List, Optional


class Job:
    def __init__(self, app_id: str):
        self.id = app_id
        self.status = "pending"            # pending | running | done | error
        self.events: List[dict] = []
        self.result: Optional[dict] = None  # the assembled ApplicationView
        self.error: Optional[str] = None
        self.survey: dict = {"status": "none"}
        self.context: Dict[str, Any] = {}   # raw inputs + stage outputs for re-offer

    def add_event(self, event: dict) -> None:
        self.events.append(event)


class JobStore:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}

    def create(self, app_id: str) -> Job:
        job = Job(app_id)
        self._jobs[app_id] = job
        return job

    def get(self, app_id: str) -> Optional[Job]:
        return self._jobs.get(app_id)

    def get_or_create(self, app_id: str) -> Job:
        return self._jobs.get(app_id) or self.create(app_id)


# Module-level single store shared by orchestration + survey (single worker).
STORE = JobStore()
