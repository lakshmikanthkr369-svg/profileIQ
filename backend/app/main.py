"""ProfileIQ API. The web app sends the user's Supabase login token; the server checks it,
applies plan and scan limits, runs the AI work and builds the resume files."""
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from . import admin, auth, billing, config, invoices
from .ai import build_fresher_resume, do_rewrite, get_suggestions, score_resume
from .ai_errors import describe_ai_error
from .limits import check_ai_rate, check_rate
from .readers import extract_text
from .resume_files import RESUME_TEMPLATES, make_docx, make_pdf, resume_preview_html

app = FastAPI(title="ProfileIQ API", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["GET", "POST", "PATCH"],
                   allow_headers=["Authorization", "Content-Type"], max_age=600)

ALLOWED_EXT = (".pdf", ".doc", ".docx")
FILE_ERRORS = {"EMPTY_RESUME", "NOT_WORD", "ENCRYPTED_DOC", "BAD_DOC", "DOC_LIB_MISSING"}


MAX_JSON_BYTES = 300 * 1024


@app.middleware("http")
async def security_headers(request, call_next):
    # Refuse oversized request bodies early (uploads are checked separately, with a friendly message).
    try:
        length = int(request.headers.get("content-length") or 0)
    except ValueError:
        length = 0
    is_json = "application/json" in request.headers.get("content-type", "")
    if (is_json and length > MAX_JSON_BYTES) or length > config.MAX_UPLOAD_BYTES + 1024 * 1024:
        return JSONResponse(status_code=413, content={"message": "That request is too large.", "ref": "too-large"})
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail), "ref": f"http-{exc.status_code}"}
    return JSONResponse(detail, status_code=exc.status_code)


def _fail(e: Exception) -> HTTPException:
    """Any failure becomes a friendly message + reference; the full detail goes to the server log."""
    info = describe_ai_error(e)
    status = 422 if (isinstance(e, ValueError) and str(e) in FILE_ERRORS) or type(e).__name__ in ("LegacyDocError",) else 502
    return HTTPException(status, info)


async def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    name = (file.filename or "").strip()
    if not name.lower().endswith(ALLOWED_EXT):
        raise HTTPException(415, {"message": "Please upload a PDF or Word (.doc, .docx) file.", "ref": "bad-type"})
    data = await file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, {"message": f"That file is too large (limit {config.MAX_UPLOAD_BYTES // 1048576} MB).", "ref": "too-large"})
    if not data:
        raise HTTPException(422, {"message": "That file is empty.", "ref": "empty-file"})
    return data, name


def _resume_text(data: bytes, name: str) -> str:
    text = extract_text(data, name)
    if not (text or "").strip():
        raise ValueError("EMPTY_RESUME")
    return text


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/v1/me")
def me(user: dict = Depends(auth.current_user)):
    profile = auth.sync_profile_details(user, auth.get_profile(user["id"]))
    if profile:
        profile = auth.reset_scans_if_needed(profile)
    pro = auth.is_pro(profile)
    return {"id": user["id"], "email": user["email"], "full_name": (profile or {}).get("full_name") or user.get("full_name"),
            "is_pro": pro,
            "scans_left": None if pro else auth.free_scans_left(profile),
            "pro_expires_at": (profile or {}).get("pro_expires_at") if pro else None,
            "plan_ended_on": None if pro else (profile or {}).get("pro_expires_at") if (profile or {}).get("razorpay_subscription_id") else None,
            "cancels_at_period_end": pro and (profile or {}).get("subscription_status") == "cancel_at_cycle_end",
            "has_billing": pro or bool((profile or {}).get("razorpay_subscription_id")),
            "has_mobile": bool(billing.normalize_mobile((profile or {}).get("phone")))}


@app.get("/v1/templates")
def templates():
    return {"templates": list(RESUME_TEMPLATES.keys())}


@app.post("/v1/score")
async def score(resume: UploadFile = File(...), jd: str = Form(...), user: dict = Depends(auth.current_user)):
    if not jd.strip():
        raise HTTPException(422, {"message": "Paste a job description to continue.", "ref": "no-jd"})
    data, name = await _read_upload(resume)
    profile = auth.get_profile(user["id"])
    if not profile:
        raise HTTPException(409, {"message": "We couldn't load your account. Please sign out and in again.", "ref": "no-profile"})
    profile = auth.reset_scans_if_needed(profile)
    pro = auth.is_pro(profile)
    if not pro and auth.free_scans_left(profile) <= 0:
        raise HTTPException(402, {"message": "You have used all 3 free scans this month. Upgrade to Pro for unlimited scans.", "ref": "no-scans"})
    check_ai_rate(user["id"])
    try:
        text = _resume_text(data, name)
        scored = score_resume(text, jd)
        scored["suggestions"] = get_suggestions(text, jd, scored["score"], scored["missing"])
    except Exception as e:  # noqa: BLE001 - every failure is turned into a friendly message
        raise _fail(e)
    used = auth.record_scan(profile) if not pro else None
    scored["scans_left"] = None if pro else max(0, config.FREE_SCANS_PER_MONTH - used)
    return scored


def _rewritten_text(d: dict) -> str:
    parts = [d.get("name", ""), d.get("title", ""), d.get("contact", ""), d.get("summary", "")]
    parts += [f"{c.get('label', '')} {c.get('value', '')}" for c in d.get("competencies", [])]
    for j in d.get("experience", []):
        parts.append(f"{j.get('title', '')} {j.get('company', '')} {j.get('dates', '')}")
        parts += j.get("bullets", [])
    parts += [f"{s.get('label', '')} {s.get('value', '')}" for s in d.get("skills", [])]
    parts += list(d.get("achievements", []))
    parts += [d.get("education", ""), d.get("certifications", "")]
    return "\n".join(str(p) for p in parts if p)


def _require_pro(user: dict) -> dict:
    profile = auth.get_profile(user["id"])
    if not auth.is_pro(profile):
        raise HTTPException(402, {"message": "This is a Pro feature. Upgrade to Pro to use it.", "ref": "pro-only"})
    return profile


@app.post("/v1/rewrite")
async def rewrite(resume: UploadFile = File(...), jd: str = Form(...), user: dict = Depends(auth.current_user)):
    if not jd.strip():
        raise HTTPException(422, {"message": "Paste a job description to continue.", "ref": "no-jd"})
    data, name = await _read_upload(resume)
    _require_pro(user)
    check_ai_rate(user["id"])
    try:
        text = _resume_text(data, name)
        result = do_rewrite(text, jd)
        after = score_resume(_rewritten_text(result), jd)
    except Exception as e:  # noqa: BLE001
        raise _fail(e)
    return {"data": result, "after_score": after["score"], "after_matched": after["matched"], "after_missing": after["missing"]}


class FresherIn(BaseModel):
    profile: dict[str, Any]
    jd: str


@app.post("/v1/fresher")
def fresher(body: FresherIn, user: dict = Depends(auth.current_user)):
    _require_pro(user)
    p = body.profile
    missing = [label for key, label in (("full_name", "Full Name"), ("email", "Email"), ("degree", "Degree"),
                                        ("institute", "Institute"), ("key_skills", "Key Skills")) if not p.get(key)]
    if not body.jd.strip():
        missing.append("Job Description")
    if missing:
        raise HTTPException(422, {"message": "Please fill in: " + ", ".join(missing), "ref": "missing-fields"})
    check_ai_rate(user["id"])
    try:
        return {"data": build_fresher_resume(p, body.jd)}
    except Exception as e:  # noqa: BLE001
        raise _fail(e)


class FileIn(BaseModel):
    data: dict[str, Any]
    template: str = "Bold"
    format: str = "pdf"


def _check_template(t: str) -> str:
    if t not in RESUME_TEMPLATES:
        raise HTTPException(422, {"message": "Unknown resume format.", "ref": "bad-template"})
    return t


@app.post("/v1/resume/file")
def resume_file(body: FileIn, user: dict = Depends(auth.current_user)):
    _require_pro(user)
    check_rate(f"file:{user['id']}", 30, 600, "You're going a little fast. Please wait a few minutes and try again.")
    tpl = _check_template(body.template)
    try:
        if body.format == "docx":
            return Response(make_docx(body.data, tpl), media_type=
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            headers={"Content-Disposition": 'attachment; filename="ProfileIQ_Resume.docx"'})
        if body.format == "pdf":
            return Response(make_pdf(body.data, tpl), media_type="application/pdf",
                            headers={"Content-Disposition": 'attachment; filename="ProfileIQ_Resume.pdf"'})
    except Exception as e:  # noqa: BLE001
        raise _fail(e)
    raise HTTPException(422, {"message": "Choose PDF or DOCX.", "ref": "bad-format"})


@app.post("/v1/resume/preview")
def resume_preview(body: FileIn, user: dict = Depends(auth.current_user)):
    _require_pro(user)
    check_rate(f"preview:{user['id']}", 120, 600, "You're going a little fast. Please wait a few minutes and try again.")
    try:
        return {"html": resume_preview_html(body.data, _check_template(body.template))}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise _fail(e)


class SubscribeIn(BaseModel):
    mobile: str | None = None


class ReconcileIn(BaseModel):
    subscription_id: str


@app.post("/v1/billing/subscribe")
def subscribe(body: SubscribeIn, user: dict = Depends(auth.current_user)):
    check_rate(f"subscribe:{user['id']}", 10, 3600, "Too many checkout attempts. Please wait a while and try again.")
    return billing.create_subscription(user, auth.get_profile(user["id"]), body.mobile)


@app.post("/v1/billing/confirm")
def confirm(body: ReconcileIn, user: dict = Depends(auth.current_user)):
    check_rate(f"confirm:{user['id']}", 60, 600, "Too many requests. Please wait a minute and try again.")
    if not body.subscription_id.startswith("sub_") or len(body.subscription_id) > 40:
        raise HTTPException(422, {"message": "Invalid subscription.", "ref": "bad-sub"})
    return {"status": billing.reconcile(user, body.subscription_id)}


@app.post("/v1/billing/cancel")
def cancel(user: dict = Depends(auth.current_user)):
    billing.cancel(user, auth.get_profile(user["id"]))
    return {"ok": True}


@app.get("/v1/invoices")
def invoice_list(user: dict = Depends(auth.current_user)):
    return {"invoices": invoices.list_invoices(user["id"])}


@app.post("/v1/invoices/{invoice_id}/email")
def invoice_email(invoice_id: int, user: dict = Depends(auth.current_user)):
    return {"sent_to": invoices.resend_invoice(user, invoice_id)}


class SupportIn(BaseModel):
    type: str = "Feedback"
    message: str


@app.post("/v1/support")
def support(body: SupportIn, user: dict = Depends(auth.current_user)):
    check_rate(f"support:{user['id']}", 5, 3600, "You've sent several messages already. Please wait a while before sending another.")
    invoices.submit_support(user, body.type, body.message)
    return {"ok": True}


# ── Owner-only admin ──
@app.get("/v1/admin/me")
def admin_me(a: dict = Depends(admin.require_admin)):
    return {"ok": True, "email": a["email"]}


@app.get("/v1/admin/users")
def admin_users(q: str = "", filter: str = "all", offset: int = 0, a: dict = Depends(admin.require_admin)):
    return admin.list_users(q, filter, offset)


@app.get("/v1/admin/stats")
def admin_stats(a: dict = Depends(admin.require_admin)):
    return admin.stats()


@app.get("/v1/admin/users/{user_id}")
def admin_user(user_id: str, a: dict = Depends(admin.require_admin)):
    return admin.get_user(user_id)


class AdminUserEdit(BaseModel):
    full_name: str | None = None
    phone: str | None = None


@app.patch("/v1/admin/users/{user_id}")
def admin_user_edit(user_id: str, body: AdminUserEdit, a: dict = Depends(admin.require_admin)):
    return admin.update_user(a, user_id, body.model_dump())
