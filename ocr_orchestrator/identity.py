"""Pure applicant-name resolution (spec §6/§7).

v1 derives only the name, in precedence order slip -> mutasi -> sk. The KTP
service (name / birth_date / nik) is a follow-on. The SK shape varies, so the
SK lookup recursively searches for a worker-name key at any depth.
"""
from __future__ import annotations

from typing import Any, Optional

_SK_NAME_KEYS = ("worker_name", "nama_pekerja")


def _search_key(node: Any, keys: tuple[str, ...]) -> Optional[str]:
    """First non-empty string value under any of ``keys``, searched recursively."""
    if isinstance(node, dict):
        for k in keys:
            v = node.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in node.values():
            found = _search_key(v, keys)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _search_key(item, keys)
            if found:
                return found
    return None


def resolve_applicant_name(
    slip_docs: list[dict[str, Any]],
    mutasi_accounts: list[dict[str, Any]],
    sk_responses: list[dict[str, Any]],
) -> tuple[Optional[str], Optional[str]]:
    """Return ``(name, source)`` where source is 'slip' | 'mutasi' | 'sk' | None."""
    for d in slip_docs:
        v = d.get("worker_name")
        if isinstance(v, str) and v.strip():
            return v.strip(), "slip"
    for acc in mutasi_accounts:
        v = acc.get("nama")
        if isinstance(v, str) and v.strip():
            return v.strip(), "mutasi"
    for sk in sk_responses:
        v = _search_key(sk, _SK_NAME_KEYS)
        if v:
            return v, "sk"
    return None, None
