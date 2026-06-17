"""ocr_classifier (:5001) -> UI ClassifyResult[].

Verification finding (spec §3): classification labels match; the classifier does
NOT return KTP fields, so `extract` is omitted (identity comes from the fixture).
Raw row: {filename, document_type, confidence, ...} (Explore-confirmed).
"""

from typing import Any, List

from nilam_backend.app.settings import get_settings
from nilam_backend.core.http import post_files

LABELS = {"ktp", "kk", "sk", "slip", "mutasi", "unknown"}


def normalize_classify(raw: dict) -> List[dict]:
    out: List[dict] = []
    for r in raw.get("results", []) or []:
        doc_type = r.get("document_type", "unknown")
        out.append({
            "fileName": r.get("filename", ""),
            "type": doc_type if doc_type in LABELS else "unknown",
            "confidence": str(r.get("confidence", "")),
        })
    return out


async def fetch_classify(files: Any) -> List[dict]:
    s = get_settings()
    raw = await post_files(
        "{}/classify-batch".format(s.classifier_url), files=files, service="classifier"
    )
    return normalize_classify(raw)
