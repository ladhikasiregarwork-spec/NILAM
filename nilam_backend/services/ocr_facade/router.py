"""Unified-classifier compatibility facade (upload-time OCR — backend_info.md §2).

The nilam-prototype upload step (`hooks/useNilamFlow.classifyAndUpload`) posts to a
single "classifier" service exposing `/classify-batch`, `/extract-{ktp,kk,slip,sk,
mutasi}` and `/slik`. That monolith does not exist in this repo; the real OCR is
split across the `ocr_*` services. This router re-exposes that one API surface and
fans out to the split services via `core/upstream`, so the frontend can point its
`CLASSIFIER_URL` at this backend and route upload-time OCR *through the backend*.

Endpoints are mounted at the ROOT (no `/api` prefix) on purpose: the BFF appends
these paths directly onto `CLASSIFIER_URL` (e.g. `${CLASSIFIER_URL}/extract-slip`).

Degradation contract (matches the BFF routes): only `/classify-batch` is a hard
gate in the UI; the rest are best-effort, so upstream failures here return
`{ok: false, error}` with 502 and the UI degrades quietly. KTP/KK and SLIK have no
real backend yet, so they reuse the existing seeded fixtures (identity / slik).
"""

from typing import List

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import JSONResponse

from nilam_backend.app.settings import get_settings
from nilam_backend.core.envelope import err, ok
from nilam_backend.core.http import UpstreamError, post_files
from nilam_backend.core.upstream.mutasi import normalize_mutasi
from nilam_backend.core.upstream.sk import normalize_sk
from nilam_backend.core.upstream.slip import normalize_slip
from nilam_backend.services.identity.logic import get_identity
from nilam_backend.services.slik.logic import get_slik

router = APIRouter(tags=["ocr-facade"])

# Every ocr_* service accepts the multipart batch field `files` (verified per
# service signature, same as services/orchestration/ingest.py).
_FILE_FIELD = "files"

# Slip/mutasi extraction runs PaddleOCR + an LLM pass, well over the 30s default.
_EXTRACT_TIMEOUT = 180.0


async def _httpx_files(files: List[UploadFile]) -> list:
    """Read UploadFiles into an httpx multipart list under the shared `files` field."""
    out = []
    for f in files:
        content = await f.read()
        out.append(
            (_FILE_FIELD, (f.filename or "dokumen.pdf", content, f.content_type or "application/pdf"))
        )
    return out


def _first(value):
    """normalize_mutasi returns fileName as a list; the UI wants a single name."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


@router.post("/classify-batch")
async def classify_batch(files: List[UploadFile] = File(...)):
    """Proxy to ocr_classifier; pass its raw `{results: [...]}` straight through —
    the BFF maps `document_type`/`fields` itself."""
    s = get_settings()
    try:
        raw = await post_files(
            "{}/classify-batch".format(s.classifier_url),
            files=await _httpx_files(files),
            timeout=_EXTRACT_TIMEOUT,
            service="classifier",
        )
    except UpstreamError as e:
        return JSONResponse(status_code=502, content=err("classifier: {}".format(e.detail)))
    return raw


@router.post("/extract-slip")
async def extract_slip(files: List[UploadFile] = File(...)):
    """ocr_slip /parse -> {ok, records: [...]} (SlipGajiExtract)."""
    s = get_settings()
    try:
        raw = await post_files(
            "{}/parse".format(s.slip_url),
            files=await _httpx_files(files),
            timeout=_EXTRACT_TIMEOUT,
            service="slip",
        )
    except UpstreamError as e:
        return JSONResponse(status_code=502, content=err("slip: {}".format(e.detail)))
    return ok(**normalize_slip(raw))


@router.post("/extract-sk")
async def extract_sk(file: UploadFile = File(...)):
    """ocr_sk /parse -> {ok, fields, filename} (SkPerusahaanExtract)."""
    s = get_settings()
    try:
        raw = await post_files(
            "{}/parse".format(s.sk_url),
            files=await _httpx_files([file]),
            timeout=_EXTRACT_TIMEOUT,
            service="sk",
        )
    except UpstreamError as e:
        return JSONResponse(status_code=502, content=err("sk: {}".format(e.detail)))
    fields = normalize_sk(raw)
    return ok(fields=fields, filename=fields.get("fileName") or file.filename)


@router.post("/extract-mutasi")
async def extract_mutasi(files: List[UploadFile] = File(...)):
    """ocr_mutasi extract-batch -> {ok, fields, filename} (MutasiExtract)."""
    s = get_settings()
    try:
        raw = await post_files(
            "{}/api/v1/mutations/extract-batch".format(s.mutasi_url),
            files=await _httpx_files(files),
            timeout=_EXTRACT_TIMEOUT,
            service="mutasi",
        )
    except UpstreamError as e:
        return JSONResponse(status_code=502, content=err("mutasi: {}".format(e.detail)))
    fields = normalize_mutasi(raw)
    filename = _first(fields.get("fileName")) or (files[0].filename if files else None)
    return ok(fields=fields, filename=filename)


@router.post("/extract-ktp")
async def extract_ktp(file: UploadFile = File(...), who: str = Query("nasabah")):
    """KTP — FIXTURE (no real KTP OCR backend exists). Returns the seeded record;
    the uploaded file is accepted but not parsed. See services/identity."""
    fields = get_identity("ktp", who)
    return ok(fields=fields, filename=fields.get("fileName") or file.filename)


@router.post("/extract-kk")
async def extract_kk(file: UploadFile = File(...)):
    """KK — FIXTURE (no real KK OCR backend exists). See services/identity."""
    fields = get_identity("kk")
    return ok(fields=fields, filename=fields.get("fileName") or file.filename)


@router.get("/slik")
async def slik(nik: str = Query(default="")):
    """SLIK — FIXTURE (no real bureau feed). Seeded report keyed by NIK."""
    if not nik:
        return JSONResponse(status_code=400, content=err("nik wajib diisi"))
    return ok(**get_slik(nik))
