"""Manual end-to-end smoke test (NEEDS the four OCR services running + .env).

Usage (from repo root, with venv active and services up):
    python ocr_orchestrator/smoke_orchestrator.py path/to/*.pdf

Submits the bundle, polls until done, prints the income breakdown.
"""
from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8500"


def main(paths: list[str]) -> int:
    if not paths:
        print("Pass at least one PDF path.")
        return 2
    files = [("files", (p.split("/")[-1].split("\\")[-1], open(p, "rb"), "application/pdf"))
             for p in paths]
    r = httpx.post(f"{BASE}/api/v1/applications",
                   files=files, data={"bonus_accept_pct": "0.5"}, timeout=60)
    print("POST", r.status_code, r.json())
    if r.status_code != 202:
        return 1
    status_url = BASE + r.json()["status_url"]
    for _ in range(600):
        g = httpx.get(status_url, timeout=30).json()
        if g["status"] in ("completed", "failed"):
            print("FINAL status:", g["status"])
            if g.get("result"):
                print("income:", g["result"]["income"])
                print("applicant:", g["result"]["applicant"])
                print("audit:", g["result"]["audit"])
            else:
                print("error:", g.get("error"))
            return 0 if g["status"] == "completed" else 1
        time.sleep(1)
    print("timed out waiting for job")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
