from fastapi import FastAPI

from nilam_backend.core.envelope import ok

app = FastAPI(title="NILAM Backend", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return ok(service="nilam_backend")


# Service routers are mounted here as they are built (Tasks 3, 4, 6).
