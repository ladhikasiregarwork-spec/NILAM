"""Raw-bundle ingestion — the orchestrator owns OCR (design §5 `ocr` node).

Takes the raw uploaded PDFs, classifies them via `ocr_classifier`, routes each to
the matching extractor (`ocr_slip` / `ocr_mutasi` / `ocr_sk`), appraises NPW from
the agunan via `house_fair_market_value`, and assembles a `ProcessRequest` the
proven sync `run_pipeline` consumes. The OCR services all expose the upload field
name `files` (verified against each service signature).

Upstream failures degrade, not 500 (design §7): a failed stage records its error in
the returned `audit["errors"]` and falls back to an empty extract / npw=0, so the
pipeline still completes and the ApplicationView assembles with that piece empty.
"""

from typing import Any, Dict, List, Optional, Tuple

from nilam_backend.core.http import UpstreamError
from nilam_backend.core.upstream.classifier import fetch_classify
from nilam_backend.core.upstream.mutasi import fetch_mutasi
from nilam_backend.core.upstream.npw import fetch_npw
from nilam_backend.core.upstream.sk import fetch_sk
from nilam_backend.core.upstream.slip import fetch_slip
from nilam_backend.domain.agunan import AgunanKlasifikasi
from nilam_backend.domain.documents import MutasiExtract, SlipRecord

from .models import AgunanModel, OcrInput, ProcessRequest, UserInputModel

# One uploaded file: (filename, content bytes, content-type).
Upload = Tuple[str, bytes, str]

# OCR services that accept the multipart batch field `files` (verified per service).
_FILE_FIELD = "files"


def _httpx_files(uploads: List[Upload]) -> list:
    """Build an httpx multipart `files` list under the shared `files` field."""
    return [(_FILE_FIELD, (name, content, ctype)) for (name, content, ctype) in uploads]


async def ingest_bundle(uploads: List[Upload], meta: Dict[str, Any]) -> Tuple[ProcessRequest, dict]:
    """Classify + extract the raw bundle and assemble a ProcessRequest.

    `meta` carries the non-file inputs: {joint, userInput, agunan, agunanKlas}.
    Returns (ProcessRequest, audit) where audit["errors"] lists degraded stages.
    """
    errors: List[str] = []

    async def guarded(coro, fallback):
        """Await an upstream call; on UpstreamError record it and return fallback."""
        try:
            return await coro
        except UpstreamError as e:
            errors.append(str(e))
            return fallback

    # 1. Classify every file (order preserved), then group by detected type.
    classified = await guarded(fetch_classify(_httpx_files(uploads)), [])
    groups: Dict[str, List[Upload]] = {}
    for up, c in zip(uploads, classified):
        groups.setdefault(c.get("type", "unknown"), []).append(up)

    # 2. Route each group to its extractor (only when files of that type exist).
    mutasi_raw: dict = {}
    slip_raw: dict = {"records": []}
    if groups.get("mutasi"):
        mutasi_raw = await guarded(fetch_mutasi(_httpx_files(groups["mutasi"])), {})
    if groups.get("slip"):
        slip_raw = await guarded(fetch_slip(_httpx_files(groups["slip"])), {"records": []})
    if groups.get("sk"):
        # SK is not used by the calc pipeline; fetched for completeness / audit only.
        await guarded(fetch_sk(_httpx_files(groups["sk"])), {})

    mutasi = MutasiExtract(**mutasi_raw) if mutasi_raw else MutasiExtract()
    slip_records = [SlipRecord(**r) for r in (slip_raw.get("records") or [])]

    # 3. Appraise NPW from the agunan (skip when land area is unknown).
    agunan_meta = meta.get("agunan") or {}
    npw_value: float = 0
    luas_tanah = agunan_meta.get("luasTanah") or 0
    if luas_tanah and luas_tanah > 0:
        npw_raw = await guarded(
            fetch_npw(
                luas_tanah=luas_tanah,
                luas_bangunan=agunan_meta.get("luasBangunan"),
                kode_pos=agunan_meta.get("kodepos"),
                kelurahan=agunan_meta.get("kelurahan"),
            ),
            {},
        )
        npw_value = npw_raw.get("fairValue") or 0

    # 4. Assemble the ProcessRequest the sync pipeline consumes.
    klas_meta: Optional[dict] = meta.get("agunanKlas")
    req = ProcessRequest(
        joint=bool(meta.get("joint", False)),
        uploads=[name for (name, _c, _t) in uploads],
        ocr=OcrInput(mutasi=mutasi, slipRecords=slip_records),
        userInput=UserInputModel(**(meta.get("userInput") or {})),
        agunan=AgunanModel(**agunan_meta),
        agunanKlas=AgunanKlasifikasi(**klas_meta) if klas_meta else AgunanKlasifikasi(),
        npw=npw_value,
    )
    return req, {"errors": errors}
