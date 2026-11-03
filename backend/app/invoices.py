"""Invoice list + email re-send, and the support form. Always scoped to the logged-in user."""
import html
import re
import time
from datetime import datetime, timezone

import requests
from fastapi import HTTPException

from . import auth, config

COOLDOWN_SECONDS = 60
TICKET_TYPES = ("Feedback", "Bug Report", "Feature Request", "Other")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _rest(path: str, **kw):
    try:
        return requests.request(kw.pop("method", "GET"), f"{config.SUPABASE_URL}/rest/v1/{path}",
                                headers={**auth._service_headers(), **kw.pop("headers", {})}, timeout=15, **kw)
    except requests.RequestException:
        raise HTTPException(502, {"message": "We couldn't reach the database. Please try again shortly.", "ref": "db-network"})


def list_invoices(user_id: str, limit: int = 12) -> list[dict]:
    if not _UUID.match(user_id or ""):
        raise HTTPException(400, {"message": "Invalid account.", "ref": "bad-user"})
    r = _rest(f"invoices?user_id=eq.{user_id}&select=id,invoice_number,issued_at,amount_paise,currency,payment_method,emailed_at"
              f"&order=id.desc&limit={limit}")
    if r.status_code != 200:
        raise HTTPException(502, {"message": "We couldn't load your invoices right now.", "ref": f"inv-{r.status_code}"})
    return r.json()


def _send_email(payload: dict, idem: str) -> bool:
    if not config.RESEND_API_KEY:
        return False
    try:
        r = requests.post("https://api.resend.com/emails", json=payload, timeout=20,
                          headers={"Authorization": f"Bearer {config.RESEND_API_KEY}", "Idempotency-Key": idem})
    except requests.RequestException:
        return False
    return r.status_code in (200, 201)


def resend_invoice(user: dict, invoice_id: int) -> str:
    """Emails the stored invoice to the address on that invoice (never one supplied by the browser)."""
    r = _rest(f"invoices?id=eq.{int(invoice_id)}&user_id=eq.{user['id']}"
              "&select=id,invoice_number,customer_email,razorpay_payment_id,html_body,text_body,emailed_at,last_resent_at,resend_count&limit=1")
    if r.status_code != 200:
        raise HTTPException(502, {"message": "We couldn't load that invoice right now. Please try again shortly.", "ref": f"inv-{r.status_code}"})
    rows = r.json()
    if not rows:
        raise HTTPException(404, {"message": "Invoice not found.", "ref": "no-invoice"})
    inv = rows[0]
    if not inv.get("html_body"):
        raise HTTPException(409, {"message": f"We don't have a saved copy of that invoice. Please write to {config.SUPPORT_EMAIL} and we'll send it.", "ref": "no-copy"})
    last = inv.get("last_resent_at") or inv.get("emailed_at")
    if last:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(str(last).replace("Z", "+00:00"))).total_seconds()
            if age < COOLDOWN_SECONDS:
                raise HTTPException(429, {"message": "This invoice was emailed less than a minute ago. Please check your inbox (and spam folder).", "ref": "cooldown"})
        except ValueError:
            pass
    to = inv.get("customer_email") or user.get("email")
    if not to:
        raise HTTPException(409, {"message": "We don't have an email address on file for this invoice.", "ref": "no-email"})
    payload = {"from": config.INVOICE_FROM, "to": [to], "reply_to": config.SUPPORT_EMAIL,
               "subject": f"Your ProfileIQ invoice {inv['invoice_number']} (copy)", "html": inv["html_body"]}
    if inv.get("text_body"):
        payload["text"] = inv["text_body"]
    if not _send_email(payload, f"invoice-{inv['razorpay_payment_id']}-resend-{int(time.time() // 60)}"):
        raise HTTPException(502, {"message": "We couldn't send the email right now. Please try again shortly.", "ref": "email-failed"})
    now = datetime.now(timezone.utc).isoformat()
    patch = {"last_resent_at": now, "resend_count": int(inv.get("resend_count") or 0) + 1}
    if not inv.get("emailed_at"):
        patch["emailed_at"] = now
    _rest(f"invoices?id=eq.{int(invoice_id)}&user_id=eq.{user['id']}", method="PATCH", json=patch, headers={"Prefer": "return=minimal"})
    return to


def submit_support(user: dict, ticket_type: str, message: str) -> None:
    if ticket_type not in TICKET_TYPES:
        raise HTTPException(422, {"message": "Choose a type.", "ref": "bad-type"})
    msg = message.strip()
    if not msg:
        raise HTTPException(422, {"message": "Please enter a message.", "ref": "no-message"})
    r = _rest("support_tickets", method="POST", json={"user_email": user["email"], "type": ticket_type, "message": msg[:4000]},
              headers={"Prefer": "return=minimal"})
    if r.status_code not in (200, 201):
        raise HTTPException(502, {"message": "We couldn't submit that. Please try again.", "ref": f"sup-{r.status_code}"})
    e, t, m = (html.escape(x) for x in (user["email"], ticket_type, msg[:4000]))
    _send_email({"from": "ProfileIQ <noreply@profileiq.co.in>", "to": [config.SUPPORT_EMAIL], "reply_to": user["email"],
                 "subject": f"[ProfileIQ Support] {ticket_type} from {user['email']}"[:200],
                 "html": f"<p><b>From:</b> {e}</p><p><b>Type:</b> {t}</p><p><b>Message:</b><br>{m.replace(chr(10), '<br>')}</p>"},
                f"support-{user['id']}-{int(time.time())}")
