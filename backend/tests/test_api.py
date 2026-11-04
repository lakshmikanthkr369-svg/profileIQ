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
    from app import limits
    limits._calls.clear()
    main.app.dependency_overrides[auth.current_user] = lambda: USER
    state = {"profile": {"id": "u1", "plan": "free", "scans_used": 0}, "recorded": 0}
    monkeypatch.setattr(auth, "get_profile", lambda uid: dict(state["profile"]))
    monkeypatch.setattr(auth, "reset_scans_if_needed", lambda p: p)
    monkeypatch.setattr(auth, "sync_profile_details", lambda u, p: p)

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


class _Resp:
    def __init__(self, status=200, body=None): self.status_code, self._b = status, body or []
    def json(self): return self._b


def test_sync_fills_only_blanks_and_for_own_user(monkeypatch):
    calls = []
    monkeypatch.setattr(auth.requests, "patch", lambda url, **kw: calls.append(kw) or _Resp(204))
    user = {"id": "u1", "email": "a@b.com", "full_name": "Asha K", "mobile": "+919876543210"}
    out = auth.sync_profile_details(user, {"id": "u1", "email": "a@b.com", "full_name": "Existing", "phone": ""})
    assert calls[0]["json"] == {"phone": "+919876543210"}          # name kept, blank phone filled
    assert calls[0]["params"]["id"] == "eq.u1" and out["phone"] == "+919876543210" and out["full_name"] == "Existing"


def test_sync_creates_missing_profile(monkeypatch):
    monkeypatch.setattr(auth.requests, "post", lambda url, **kw: _Resp(201, [dict(kw["json"])]))
    out = auth.sync_profile_details({"id": "u9", "email": "n@x.com", "full_name": "N", "mobile": ""}, None)
    assert out["id"] == "u9" and out["plan"] == "free" and out["full_name"] == "N" and "phone" not in out


# ── billing ──
def _fake_rzp(monkeypatch, sub=None):
    from app import billing
    calls = []
    monkeypatch.setattr(billing.config, "RAZORPAY_KEY_ID", "rzp_test_x")
    monkeypatch.setattr(billing.config, "RAZORPAY_KEY_SECRET", "s")
    monkeypatch.setattr(billing.config, "RAZORPAY_PLAN_ID", "plan_x")
    monkeypatch.setattr(billing, "_patch_profile", lambda uid, f: calls.append(("patch", f)))

    def rzp(method, path, **kw):
        calls.append((method, path, kw))
        if method == "POST" and path == "/subscriptions":
            return {"id": "sub_123"}
        return sub or {}
    monkeypatch.setattr(billing, "_rzp", rzp)
    return calls


def test_subscribe_needs_valid_mobile(client, monkeypatch):
    _fake_rzp(monkeypatch)
    r = client.post("/v1/billing/subscribe", json={"mobile": "12345"})
    assert r.status_code == 422 and r.json()["ref"] == "bad-mobile"


def test_subscribe_creates_with_user_id_in_notes(client, monkeypatch):
    calls = _fake_rzp(monkeypatch)
    r = client.post("/v1/billing/subscribe", json={"mobile": "098765 43210"})
    assert r.status_code == 200 and r.json()["subscription_id"] == "sub_123" and r.json()["contact"] == "9876543210"
    assert "key_secret" not in r.text and "secret" not in r.text.lower()
    created = [c for c in calls if c[0] == "POST"][0][2]["json"]
    assert created["notes"]["user_id"] == "u1" and created["plan_id"] == "plan_x"


def test_subscribe_refused_when_already_pro(client, monkeypatch):
    _fake_rzp(monkeypatch)
    client.state["profile"].update(plan="pro", pro_expires_at=FUTURE)
    assert client.post("/v1/billing/subscribe", json={"mobile": "9876543210"}).status_code == 409


def test_confirm_marks_pro_only_for_own_subscription(client, monkeypatch):
    calls = _fake_rzp(monkeypatch, {"status": "active", "current_end": 4102444800, "customer_id": "cust_1", "notes": {"user_id": "u1"}})
    r = client.post("/v1/billing/confirm", json={"subscription_id": "sub_123"})
    assert r.json() == {"status": "paid"} and any(c[0] == "patch" and c[1]["plan"] == "pro" for c in calls)
    calls2 = _fake_rzp(monkeypatch, {"status": "active", "notes": {"user_id": "someone-else"}})
    assert client.post("/v1/billing/confirm", json={"subscription_id": "sub_123"}).status_code == 403
    assert not any(c[0] == "patch" for c in calls2)


def test_confirm_pending_and_bad_id(client, monkeypatch):
    _fake_rzp(monkeypatch, {"status": "created", "notes": {"user_id": "u1"}})
    assert client.post("/v1/billing/confirm", json={"subscription_id": "sub_123"}).json() == {"status": "pending"}
    assert client.post("/v1/billing/confirm", json={"subscription_id": "../x"}).status_code == 422


def test_cancel_requires_active_subscription(client, monkeypatch):
    calls = _fake_rzp(monkeypatch)
    assert client.post("/v1/billing/cancel").status_code == 409
    client.state["profile"].update(plan="pro", pro_expires_at=FUTURE, razorpay_subscription_id="sub_123")
    assert client.post("/v1/billing/cancel").status_code == 200
    assert any(c[0] == "POST" and c[1] == "/subscriptions/sub_123/cancel" for c in calls)


# ── invoices + support ──
def _fake_db(monkeypatch, rows, status=200):
    from app import invoices
    seen = []

    class R:
        def __init__(s, st, data): s.status_code, s._d = st, data
        def json(s): return s._d

    def rest(path, **kw):
        seen.append((kw.get("method", "GET"), path, kw.get("json")))
        return R(status, rows if kw.get("method", "GET") == "GET" else {})
    monkeypatch.setattr(invoices, "_rest", rest)
    sent = []
    monkeypatch.setattr(invoices, "_send_email", lambda p, k: sent.append(p) or True)
    return seen, sent


def test_invoice_list_is_scoped_to_user(client, monkeypatch):
    seen, _ = _fake_db(monkeypatch, [{"id": 1, "invoice_number": "PIQ-1"}])
    main.app.dependency_overrides[auth.current_user] = lambda: {"id": "6f1c2a3e-1111-4222-8333-444455556666", "email": "a@b.com"}
    r = client.get("/v1/invoices")
    assert r.status_code == 200 and r.json()["invoices"][0]["invoice_number"] == "PIQ-1"
    assert "user_id=eq.6f1c2a3e-1111-4222-8333-444455556666" in seen[0][1]


def test_invoice_list_rejects_bad_user_id(client, monkeypatch):
    _fake_db(monkeypatch, [])
    assert client.get("/v1/invoices").status_code == 400      # test user id "u1" is not a UUID


def test_resend_goes_to_invoice_address_and_respects_cooldown(client, monkeypatch):
    row = {"id": 1, "invoice_number": "PIQ-1", "customer_email": "owner@x.com", "razorpay_payment_id": "pay_1",
           "html_body": "<p>inv</p>", "text_body": "inv", "emailed_at": None, "last_resent_at": None, "resend_count": 0}
    seen, sent = _fake_db(monkeypatch, [row])
    r = client.post("/v1/invoices/1/email")
    assert r.status_code == 200 and r.json()["sent_to"] == "owner@x.com" and sent[0]["to"] == ["owner@x.com"]
    from datetime import datetime, timezone
    row["last_resent_at"] = datetime.now(timezone.utc).isoformat()
    assert client.post("/v1/invoices/1/email").status_code == 429


def test_resend_without_saved_copy_and_unknown_invoice(client, monkeypatch):
    _fake_db(monkeypatch, [{"id": 1, "invoice_number": "x", "html_body": None, "razorpay_payment_id": "p"}])
    assert client.post("/v1/invoices/1/email").json()["ref"] == "no-copy"
    _fake_db(monkeypatch, [])
    assert client.post("/v1/invoices/9/email").status_code == 404


def test_support_validates_and_escapes(client, monkeypatch):
    seen, sent = _fake_db(monkeypatch, [])
    assert client.post("/v1/support", json={"type": "Hack", "message": "x"}).status_code == 422
    assert client.post("/v1/support", json={"type": "Bug Report", "message": "   "}).status_code == 422
    assert client.post("/v1/support", json={"type": "Bug Report", "message": "<script>alert(1)</script>"}).status_code == 200
    assert "<script>" not in sent[0]["html"] and "&lt;script&gt;" in sent[0]["html"]


def test_support_is_rate_limited(client, monkeypatch):
    _fake_db(monkeypatch, [])
    codes = [client.post("/v1/support", json={"type": "Other", "message": "hi"}).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_oversized_json_is_refused(client):
    r = client.post("/v1/support", content=b'{"type":"Other","message":"' + b"a" * 400_000 + b'"}', headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["ref"] == "too-large"


def test_subscribe_is_rate_limited(client, monkeypatch):
    _fake_rzp(monkeypatch)
    codes = [client.post("/v1/billing/subscribe", json={"mobile": "9876543210"}).status_code for _ in range(12)]
    assert codes[9] == 200 and codes[10] == 429


def test_service_headers_support_new_and_legacy_keys(monkeypatch):
    monkeypatch.setattr(auth.config, "SUPABASE_SERVICE_KEY", "eyJlegacy.jwt.key")
    assert auth._service_headers()["Authorization"] == "Bearer eyJlegacy.jwt.key"
    monkeypatch.setattr(auth.config, "SUPABASE_SERVICE_KEY", "sb_secret_abc")
    h = auth._service_headers()
    assert h["apikey"] == "sb_secret_abc" and "Authorization" not in h


def test_me_reports_ended_plan_and_cancel_state(client):
    client.state["profile"].update(plan="pro", pro_expires_at="2020-01-01T00:00:00+00:00", razorpay_subscription_id="sub_1")
    d = client.get("/v1/me").json()
    assert d["is_pro"] is False and d["plan_ended_on"] == "2020-01-01T00:00:00+00:00"
    client.state["profile"].update(pro_expires_at=FUTURE, subscription_status="cancel_at_cycle_end")
    d = client.get("/v1/me").json()
    assert d["is_pro"] is True and d["cancels_at_period_end"] is True and d["plan_ended_on"] is None


def test_cancel_emails_owner_with_user_details_and_confirms_to_user(client, monkeypatch):
    from app import billing, invoices
    _fake_rzp(monkeypatch)
    sent = []
    monkeypatch.setattr(invoices, "_send_email", lambda p, k: sent.append(p) or True)
    monkeypatch.setattr(billing.config, "OWNER_NOTIFY_EMAIL", "owner@x.com")
    client.state["profile"].update(plan="pro", pro_expires_at=FUTURE, razorpay_subscription_id="sub_123",
                                   full_name="Asha <b>K</b>", phone="9876543210")
    assert client.post("/v1/billing/cancel").status_code == 200
    owner = [m for m in sent if m["to"] == ["owner@x.com"]][0]
    assert "9876543210" in owner["html"] and "sub_123" in owner["html"] and "&lt;b&gt;" in owner["html"] and "<b>K</b>" not in owner["html"]
    user_mail = [m for m in sent if m["to"] != ["owner@x.com"]][0]
    assert "won't renew" in user_mail["html"]
    client.state["profile"]["subscription_status"] = "cancel_at_cycle_end"
    assert client.post("/v1/billing/cancel").status_code == 409       # already cancelled: no second email


def test_cancel_succeeds_even_if_email_breaks(client, monkeypatch):
    from app import invoices
    _fake_rzp(monkeypatch)
    monkeypatch.setattr(invoices, "_send_email", lambda p, k: (_ for _ in ()).throw(RuntimeError("boom")))
    client.state["profile"].update(plan="pro", pro_expires_at=FUTURE, razorpay_subscription_id="sub_123")
    assert client.post("/v1/billing/cancel").status_code == 200
