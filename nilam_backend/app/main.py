from fastapi import FastAPI

from nilam_backend.core.envelope import ok
from nilam_backend.services.capacity.router import router as capacity_router
from nilam_backend.services.coverage.router import router as coverage_router
from nilam_backend.services.credit_score.router import router as credit_score_router
from nilam_backend.services.decision.router import router as decision_router
from nilam_backend.services.fraud.router import router as fraud_router
from nilam_backend.services.income.router import router as income_router
from nilam_backend.services.matching.router import router as matching_router
from nilam_backend.services.offering.router import router as offering_router
from nilam_backend.services.plafond.router import router as plafond_router

app = FastAPI(title="NILAM Backend", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return ok(service="nilam_backend")


app.include_router(capacity_router)
app.include_router(plafond_router)
app.include_router(offering_router)
app.include_router(income_router)
app.include_router(coverage_router)
app.include_router(matching_router)
app.include_router(credit_score_router)
app.include_router(fraud_router)
app.include_router(decision_router)
