from fastapi.testclient import TestClient

from nilam_backend.app.main import app
from nilam_backend.core.jobs import STORE

client = TestClient(app)


def test_survey_state_defaults_none_then_transitions():
    # Seed a job directly (no full pipeline needed for the survey state machine).
    job = STORE.create("survey-1")
    job.status = "done"
    assert client.get("/api/applications/survey-1/survey").json()["status"] == "none"

    appr = client.post("/api/applications/survey-1/survey",
                       json={"decision": "approved", "value": 750_000_000, "note": "layak"}).json()
    assert appr["status"] == "approved" and appr["surveyValue"] == 750_000_000 and appr["surveyNote"] == "layak"


def test_survey_invalid_decision_is_400():
    STORE.create("survey-2")
    resp = client.post("/api/applications/survey-2/survey", json={"decision": "maybe"})
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
