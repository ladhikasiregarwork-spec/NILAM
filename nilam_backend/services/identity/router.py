from fastapi import APIRouter, Query

from nilam_backend.core.envelope import ok

from .logic import get_identity

router = APIRouter()


@router.post("/api/ocr/identitas")
def identitas(
    doc_type: str = Query("ktp", alias="type"),
    who: str = Query("nasabah"),
) -> dict:
    """Fixture identity. The real route takes a multipart file; this stand-in
    selects a seeded record by `type` (ktp|kk) and `who` (nasabah|pasangan)."""
    return ok(type=doc_type, extract=get_identity(doc_type, who))
