import io
import pytest
from fastapi.testclient import TestClient
from docx import Document

from app import auth, main
from app.readers import extract_text

USER = {"id": "u1", "email": "a@b.com"}
FUTURE = "2099-01-01T00:00:00+00:00"


@pytest.fixture
def client(monkeypatch):
    main.app.dependency_overrides[auth.current_user] = lambda: USER
    state = {"profile": {"id": "u1", "plan": "free", "scans_used": 0}, "recorded": 0}
    monkeypatch.setattr(auth, "get_profile", lambda uid: dict(state["profile"]))
    monkeypatch.setattr(auth, "reset_scans_if_needed", lambda p: p)

    def rec(p):
        state["recorded"] += 1
        return int(p.get("scans_used") or 0) + 1
    monkeypatch.setattr(auth, "record_scan", rec)
    monkeypatch.setattr(main, "score_resume", lambda t, jd: {"score": 71, "matched": ["python"], "missing": ["go"]})
    monkeypatch.setattr(main, "get_suggestions", lambda *a: ["add go"])
    monkeypatch.setattr(main, "do_rewrite", lambda t, jd: {"name": "Jane", "title": "Eng", "contact": "x", "summary": "s",
        "competencies": [{"label": "A", "value": "b"}], "experience": [{"title": "t", "company": "c", "dates": "d", "bullets": ["did x"]}],
        "skills": [{"label": "L", "value": "v"}], "achievements": ["won"], "education": "BE", "certifications": ""})
    monkeypatch.setattr(main.config, "AI_CALLS_PER_WINDOW", 1000)
    c = TestClient(main.app)
    c.state = state
    yield c
    main.app.dependency_overrides.clear()


def docx_bytes(text="Jane Doe Python engineer"):
    d = Document(); d.add_paragraph(text)
    t = d.add_table(rows=1, cols=2); t.rows[0].cells[0].text = "Skills"; t.rows[0].cells[1].text = "Python, SQL"
    b = io.BytesIO(); d.save(b); return b.getvalue()


def files(name="r.docx", data=None):
    return {"resume": (name, data if data is not None else docx_bytes(), "application/octet-stream")}


def test_health_and_no_docs():
    c = TestClient(main.app)
    assert c.get("/health").json() == {"ok": True}
    assert c.get("/docs").status_code == 404


def test_requires_login():
    c = TestClient(main.app)
    r = c.post("/v1/score", files=files(), data={"jd": "x"})
    assert r.status_code == 401 and r.json()["ref"] == "auth-missing"


def test_docx_table_text_is_read():
    assert "Python, SQL" in extract_text(docx_bytes(), "r.docx")


def test_score_free_user_counts_scan(client):
    r = client.post("/v1/score", files=files(), data={"jd": "python dev"})
    assert r.status_code == 200
    j = r.json()
    assert j["score"] == 71 and j["suggestions"] == ["add go"] and j["scans_left"] == 2
    assert client.state["recorded"] == 1


def test_score_blocked_when_free_scans_used(client):
    client.state["profile"]["scans_used"] = 3
    r = client.post("/v1/score", files=files(), data={"jd": "x"})
    assert r.status_code == 402 and r.json()["ref"] == "no-scans"
    assert client.state["recorded"] == 0


def test_score_pro_is_not_counted(client):
    client.state["profile"].update(plan="pro", pro_expires_at=FUTURE, scans_used=99)
    r = client.post("/v1/score", files=files(), data={"jd": "x"})
    assert r.status_code == 200 and r.json()["scans_left"] is None and client.state["recorded"] == 0


def test_expired_pro_is_treated_as_free(client):
    client.state["profile"].update(plan="pro", pro_expires_at="2020-01-01T00:00:00+00:00")
    assert client.post("/v1/rewrite", files=files(), data={"jd": "x"}).status_code == 402


def test_rewrite_is_pro_only_then_works(client):
    r = client.post("/v1/rewrite", files=files(), data={"jd": "x"})
    assert r.status_code == 402 and r.json()["ref"] == "pro-only"
    client.state["profile"].update(plan="pro", pro_expires_at=FUTURE)
    r = client.post("/v1/rewrite", files=files(), data={"jd": "x"})
    assert r.status_code == 200 and r.json()["after_score"] == 71 and r.json()["data"]["name"] == "Jane"


@pytest.mark.parametrize("name,data,status,ref", [
    ("r.txt", b"hello", 415, "bad-type"),
    ("r.docx", b"", 422, "empty-file"),
    ("r.doc", b"<html>not word</html>", 422, "LegacyDocError"),
])
def test_bad_uploads(client, name, data, status, ref):
    r = client.post("/v1/score", files=files(name, data), data={"jd": "x"})
    assert r.status_code == status and r.json()["ref"] == ref
    assert client.state["recorded"] == 0


def test_upload_too_large(client, monkeypatch):
    monkeypatch.setattr(main.config, "MAX_UPLOAD_BYTES", 100)
    r = client.post("/v1/score", files=files("r.pdf", b"x" * 500), data={"jd": "x"})
    assert r.status_code == 413


def test_ai_failure_is_friendly_and_not_counted(client, monkeypatch):
    def boom(*a): raise RuntimeError("secret internal detail")
    monkeypatch.setattr(main, "score_resume", boom)
    r = client.post("/v1/score", files=files(), data={"jd": "x"})
    assert r.status_code == 502 and "secret" not in r.text and client.state["recorded"] == 0


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(main.config, "AI_CALLS_PER_WINDOW", 2)
    from app import limits; limits._calls.clear()
    codes = [client.post("/v1/score", files=files(), data={"jd": "x"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_files_and_preview(client):
    client.state["profile"].update(plan="pro", pro_expires_at=FUTURE)
    data = client.post("/v1/rewrite", files=files(), data={"jd": "x"}).json()["data"]
    for tpl in client.get("/v1/templates").json()["templates"]:
        pdf = client.post("/v1/resume/file", json={"data": data, "template": tpl, "format": "pdf"})
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
        dx = client.post("/v1/resume/file", json={"data": data, "template": tpl, "format": "docx"})
        assert dx.status_code == 200 and dx.content[:2] == b"PK"
        pv = client.post("/v1/resume/preview", json={"data": data, "template": tpl})
        assert pv.status_code == 200 and "Jane" in pv.json()["html"]
    assert client.post("/v1/resume/file", json={"data": data, "template": "Nope", "format": "pdf"}).status_code == 422


def test_files_need_pro(client):
    assert client.post("/v1/resume/file", json={"data": {}, "template": "Bold", "format": "pdf"}).status_code == 402


def test_fresher_validation(client):
    client.state["profile"].update(plan="pro", pro_expires_at=FUTURE)
    r = client.post("/v1/fresher", json={"profile": {"full_name": "A"}, "jd": ""})
    assert r.status_code == 422 and "Email" in r.json()["message"] and "Job Description" in r.json()["message"]


def test_cors_blocks_other_origins(client):
    ok = client.options("/v1/me", headers={"Origin": "https://app.profileiq.co.in", "Access-Control-Request-Method": "GET"})
    bad = client.options("/v1/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "https://app.profileiq.co.in"
    assert "access-control-allow-origin" not in bad.headers
