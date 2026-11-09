"""Pro subscription: create a Razorpay subscription, confirm it was paid, cancel at cycle end."""
import html
import re
from datetime import datetime, timedelta, timezone

import requests
from fastapi import HTTPException

from . import auth, config, invoices

RZP = "https://api.razorpay.com/v1"


def normalize_mobile(raw: str | None) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if re.fullmatch(r"[6-9]\d{9}", digits) else None


def _rzp(method: str, path: str, **kw):
    if not (config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET and config.RAZORPAY_PLAN_ID):
        raise HTTPException(503, {"message": "Payments are not set up yet. Please contact support.", "ref": "pay-config"})
    try:
        r = requests.request(method, f"{RZP}{path}", auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET),
                             timeout=20, **kw)
    except requests.RequestException:
        raise HTTPException(502, {"message": "We couldn't reach the payment provider. Please try again.", "ref": "pay-network"})
    if r.status_code >= 400:
        raise HTTPException(502, {"message": "The payment provider couldn't complete that request. Please try again.",
                                  "ref": f"pay-{r.status_code}"})
    return r.json()


def _patch_profile(user_id: str, fields: dict) -> None:
    requests.patch(f"{config.SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}",
                   headers={**auth._service_headers(), "Prefer": "return=minimal"}, json=fields, timeout=10)


def create_subscription(user: dict, profile: dict | None, mobile: str | None) -> dict:
    if auth.is_pro(profile):
        raise HTTPException(409, {"message": "You already have an active Pro plan.", "ref": "already-pro"})
    phone = normalize_mobile(mobile) or normalize_mobile((profile or {}).get("phone")) or normalize_mobile(user.get("mobile"))
    if not phone:
        raise HTTPException(422, {"message": "Please enter a valid 10-digit Indian mobile number to continue.", "ref": "bad-mobile"})
    if (profile or {}).get("phone") != phone:
        _patch_profile(user["id"], {"phone": phone})
    notes = {"user_id": user["id"], "email": user["email"], "phone": phone}
    name = (profile or {}).get("full_name") or user.get("full_name")
    if name:
        notes["name"] = name[:100]
    sub = _rzp("POST", "/subscriptions", json={"plan_id": config.RAZORPAY_PLAN_ID, "customer_notify": 1,
                                               "total_count": 120, "notes": notes})
    return {"subscription_id": sub["id"], "key_id": config.RAZORPAY_KEY_ID, "email": user["email"], "contact": phone}


def reconcile(user: dict, subscription_id: str) -> str:
    """Asks Razorpay for the real status; marks the user Pro when paid. Returns paid | pending | not_paid."""
    sub = _rzp("GET", f"/subscriptions/{subscription_id}")
    if (sub.get("notes") or {}).get("user_id") != user["id"]:
        raise HTTPException(403, {"message": "That payment doesn't belong to your account.", "ref": "not-yours"})
    status = sub.get("status")
    if status in ("active", "charged"):
        end = sub.get("current_end")
        expires = (datetime.fromtimestamp(end, tz=timezone.utc) + timedelta(hours=6) if end
                   else datetime.now(timezone.utc) + timedelta(days=31)).isoformat()
        _patch_profile(user["id"], {"plan": "pro", "pro_expires_at": expires, "razorpay_subscription_id": subscription_id,
                                    "razorpay_customer_id": sub.get("customer_id"), "subscription_status": status})
        return "paid"
    return "pending" if status in ("created", "authenticated", "pending") else "not_paid"


def _fmt_date(iso: str | None) -> str:
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=5, minutes=30)))
        return d.strftime("%d %b %Y")
    except (ValueError, TypeError):
        return "the end of your current period"


def _notify_cancellation(user: dict, profile: dict | None, sub_id: str) -> None:
    """Tells the owner (with the user's details) and confirms to the user. Never blocks or fails the cancel."""
    p = profile or {}
    name = p.get("full_name") or user.get("full_name") or "—"
    phone = p.get("phone") or user.get("mobile") or "—"
    ends = _fmt_date(p.get("pro_expires_at"))
    when = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y, %I:%M %p IST")
    e = html.escape
    email = p.get("email") or user["email"]   # the address on the profile (admin-corrected) wins
    rows = [("Name", name), ("Email", email), ("Mobile", phone), ("User ID", user["id"]),
            ("Subscription ID", sub_id), ("Cancelled at", when), ("Pro access until", ends)]
    table = "".join(f"<tr><td style='padding:4px 12px 4px 0;color:#666'>{e(k)}</td><td><b>{e(str(v))}</b></td></tr>" for k, v in rows)
    try:
        invoices._send_email({
            "from": "ProfileIQ <noreply@profileiq.co.in>", "to": [config.OWNER_NOTIFY_EMAIL], "reply_to": email,
            "subject": f"[ProfileIQ] Subscription cancelled - {email}"[:200],
            "html": f"<p><b>A subscriber cancelled their ProfileIQ Pro plan.</b> Renewal is switched off; they keep Pro until {e(ends)}.</p><table>{table}</table>",
        }, f"cancel-owner-{sub_id}")
        invoices._send_email({
            "from": config.INVOICE_FROM, "to": [email], "reply_to": config.SUPPORT_EMAIL,
            "subject": "Your ProfileIQ subscription is cancelled",
            "html": (f"<p>Hi {e(name) if name != '—' else 'there'},</p>"
                     f"<p>We've cancelled your ProfileIQ Pro subscription. It <b>won't renew</b>, and you'll keep Pro until <b>{e(ends)}</b>.</p>"
                     f"<p>Changed your mind? You can upgrade again any time from the app. If you have feedback on why you left, just reply to this email.</p>"
                     f"<p>— Team ProfileIQ</p>"),
        }, f"cancel-user-{sub_id}")
    except Exception:  # an email problem must never undo or fail a cancellation
        pass


def cancel(user: dict, profile: dict | None) -> None:
    sid = (profile or {}).get("razorpay_subscription_id")
    if not sid or not auth.is_pro(profile):
        raise HTTPException(409, {"message": "There is no active subscription to cancel.", "ref": "no-sub"})
    if (profile or {}).get("subscription_status") == "cancel_at_cycle_end":
        raise HTTPException(409, {"message": "This subscription is already cancelled.", "ref": "already-cancelled"})
    _rzp("POST", f"/subscriptions/{sid}/cancel", json={"cancel_at_cycle_end": 1})
    _patch_profile(user["id"], {"subscription_status": "cancel_at_cycle_end"})
    _notify_cancellation(user, profile, sid)
