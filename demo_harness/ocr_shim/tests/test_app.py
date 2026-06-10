from fastapi.testclient import TestClient

from demo_harness.ocr_shim.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_predict_markdown_matches_contract(make_text_pdf):
    pdf = make_text_pdf(["Slip Gaji Pokok 5000000"])
    r = client.post(
        "/predict/markdown",
        params={"skip_orientation": "false"},
        headers={"X-API-Key": "ignored"},
        files={"file": ("doc.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["response_code"] == 200
    assert body["request_id"].startswith("local-")
    assert "Slip Gaji Pokok 5000000" in body["data"]["markdown"]


def test_predict_markdown_blank_page_is_200_with_warning(make_blank_pdf):
    r = client.post(
        "/predict/markdown",
        files={"file": ("scan.pdf", make_blank_pdf(1), "application/pdf")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["response_code"] == 200
    assert body["data"]["markdown"] == ""
    assert body["warnings"]
