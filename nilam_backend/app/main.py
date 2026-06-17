from fastapi import FastAPI

from nilam_backend.core.envelope import ok
from nilam_backend.services.capacity.router import router as capacity_router
from nilam_backend.services.offering.router import router as offering_router
from nilam_backend.services.plafond.router import router as plafond_router

app = FastAPI(title="NILAM Backend", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return ok(service="nilam_backend")


app.include_router(capacity_router)
app.include_router(plafond_router)
app.include_router(offering_router)
