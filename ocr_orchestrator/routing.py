"""Pure routing: classifier results -> typed file buckets + DocumentResult[].

Bucketing is by ``document_type``. ktp/kk are recognized but not extracted in
v1; unknown is flagged with a warning. Both still appear in ``documents[]``."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import DocumentResult

Pdf = tuple[str, bytes]


@dataclass
class Buckets:
    slips: list[Pdf] = field(default_factory=list)
    mutasi: list[Pdf] = field(default_factory=list)
    sk: list[Pdf] = field(default_factory=list)
    ktp: list[Pdf] = field(default_factory=list)
    kk: list[Pdf] = field(default_factory=list)
    unknown: list[Pdf] = field(default_factory=list)


def route_documents(
    classifications: list[dict[str, Any]],
    files: list[Pdf],
) -> tuple[Buckets, list[DocumentResult], list[str]]:
    """Group uploaded files by classified type.

    Args:
        classifications: ocr_classifier results (``filename``, ``document_type``,
            ``confidence``).
        files: the original ``(filename, bytes)`` uploads.

    Returns:
        (buckets, document_results, warnings). One DocumentResult per file.
    """
    by_name: dict[str, bytes] = {name: data for name, data in files}
    buckets = Buckets()
    docs: list[DocumentResult] = []
    warnings: list[str] = []

    _extracted = {"slip", "mutasi", "sk"}
    _recognized = {"ktp", "kk"}

    for c in classifications:
        filename = c.get("filename", "")
        doc_type = c.get("document_type", "unknown")
        data = by_name.get(filename, b"")
        pair: Pdf = (filename, data)

        if doc_type == "slip":
            buckets.slips.append(pair)
        elif doc_type == "mutasi":
            buckets.mutasi.append(pair)
        elif doc_type == "sk":
            buckets.sk.append(pair)
        elif doc_type == "ktp":
            buckets.ktp.append(pair)
        elif doc_type == "kk":
            buckets.kk.append(pair)
        else:
            buckets.unknown.append(pair)

        if doc_type in _extracted:
            status = "extracted"
        elif doc_type in _recognized:
            status = "recognized_not_extracted"
        else:
            status = "unclassified"
            warnings.append(f"{filename!r} classified as unknown — skipped.")

        docs.append(DocumentResult(
            filename=filename, document_type=doc_type,
            confidence=c.get("confidence"), status=status,
        ))

    return buckets, docs, warnings
