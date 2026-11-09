"""Owner-only admin API: look up users and subscriptions, correct a user's name / mobile (email is read-only).
Every route requires a signed-in user whose email is in ADMIN_EMAILS. The browser never touches the
database directly; this uses the server's service key, like the rest of the API."""
import re
from datetime import datetime, timezone

import requests
from fastapi import Depends, HTTPException

from . import auth, billing, config
from .invoices import _rest, _UUID
from .limits import check_rate

LIST_COLS = "id,email,full_name,phone,plan,subscription_status,pro_expires_at,created_at,razorpay_subscription_id"
DETAIL_COLS = LIST_COLS + ",razorpay_customer_id,scans_used,scans_reset_date,pro_started_at"
FILTERS = ("all", "active", "cancelled", "free")


def require_admin(user: dict = Depends(auth.current_user)) -> dict:
    if (user.get("email") or "").strip().lower() not in config.ADMIN_EMAILS:
        print(f"[admin] refused non-admin {user.get('id')}")
        raise HTTPException(403, {"message": "This account doesn't have admin access.", "ref": "not-admin"})
    check_rate(f"admin:{user['id']}", 240, 60, "Too many requests. Please slow down for a moment.")
    return user


def status_of(p: dict) -> str:
    """free | active | cancelled (still Pro until the end date) | expired"""
    exp = p.get("pro_expires_at")
    live = False
    if p.get("plan") == "pro" and exp:
        try:
            live = datetime.fromisoformat(str(exp).replace("Z", "+00:00")) > datetime.now(timezone.utc)
        except ValueError:
            live = False
    if live:
        return "cancelled" if p.get("subscription_status") == "cancel_at_cycle_end" else "active"
    return "expired" if p.get("plan") == "pro" else "free"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count(query: str) -> int:
    r = _rest(f"profiles?select=id&{query}", method="GET", headers={"Prefer": "count=exact", "Range": "0-0"})
    try:
        return int((r.headers.get("content-range") or "*/0").split("/")[-1])
    except ValueError:
        return 0


def stats() -> dict:
    now = _now_iso().replace("+", "%2B")
    return {
        "total": _count(""),
        "active": _count(f"plan=eq.pro&pro_expires_at=gt.{now}&subscription_status=neq.cancel_at_cycle_end"),
        "cancelled": _count(f"plan=eq.pro&pro_expires_at=gt.{now}&subscription_status=eq.cancel_at_cycle_end"),
    }


def list_users(q: str = "", flt: str = "all", offset: int = 0, limit: int = 50) -> dict:
    flt = flt if flt in FILTERS else "all"
    limit = max(1, min(int(limit), 100)); offset = max(0, int(offset))
    now = _now_iso().replace("+", "%2B")
    params = [f"select={LIST_COLS}", "order=created_at.desc", f"limit={limit}", f"offset={offset}"]
    q = re.sub(r"[^\w@.+\- ]", "", q or "").strip()[:60]
    if q:
        params.append(f"or=(email.ilike.*{q}*,full_name.ilike.*{q}*,phone.ilike.*{q}*)")
    if flt == "active":
        params += ["plan=eq.pro", f"pro_expires_at=gt.{now}", "subscription_status=neq.cancel_at_cycle_end"]
    elif flt == "cancelled":
        params += ["plan=eq.pro", f"pro_expires_at=gt.{now}", "subscription_status=eq.cancel_at_cycle_end"]
    elif flt == "free":
        params.append("plan=neq.pro")
    r = _rest("profiles?" + "&".join(params))
    if r.status_code != 200:
        raise HTTPException(502, {"message": "Couldn't load users right now.", "ref": f"adm-{r.status_code}"})
    rows = r.json()
    for p in rows:
        p["status"] = status_of(p)
    return {"users": rows, "has_more": len(rows) == limit, "offset": offset}


def get_user(user_id: str) -> dict:
    if not _UUID.match(user_id or ""):
        raise HTTPException(400, {"message": "Invalid user.", "ref": "bad-user"})
    r = _rest(f"profiles?id=eq.{user_id}&select={DETAIL_COLS}&limit=1")
    if r.status_code != 200:
        raise HTTPException(502, {"message": "Couldn't load that user.", "ref": f"adm-{r.status_code}"})
    rows = r.json()
    if not rows:
        raise HTTPException(404, {"message": "User not found.", "ref": "no-user"})
    p = rows[0]; p["status"] = status_of(p)
    inv = _rest(f"invoices?user_id=eq.{user_id}&select=id,invoice_number,issued_at,amount_paise,currency,payment_method,"
                "emailed_at,customer_name,customer_email&order=id.desc&limit=24")
    return {"user": p, "invoices": inv.json() if inv.status_code == 200 else []}


def clean_changes(body: dict) -> dict:
    out: dict = {}
    if body.get("full_name") is not None:
        n = re.sub(r"\s+", " ", str(body["full_name"])).strip()
        if not (2 <= len(n) <= 80) or re.search(r"[<>\x00-\x1f]", n):
            raise HTTPException(422, {"message": "Name must be 2–80 characters with no special symbols like < >.", "ref": "bad-name"})
        out["full_name"] = n
    if body.get("phone") is not None and str(body["phone"]).strip():
        ph = billing.normalize_mobile(str(body["phone"]))
        if not ph:
            raise HTTPException(422, {"message": "Mobile must be a valid 10-digit Indian number.", "ref": "bad-mobile"})
        out["phone"] = ph
    if not out:
        raise HTTPException(422, {"message": "Nothing to update.", "ref": "no-change"})
    return out


def update_user(admin: dict, user_id: str, body: dict) -> dict:
    current = get_user(user_id)["user"]
    changes = {k: v for k, v in clean_changes(body).items() if (current.get(k) or "") != v}
    if not changes:
        raise HTTPException(422, {"message": "Nothing changed.", "ref": "no-change"})
    r = _rest(f"profiles?id=eq.{user_id}", method="PATCH", headers={"Prefer": "return=minimal"}, json=changes)
    if r.status_code not in (200, 204):
        raise HTTPException(502, {"message": "Couldn't save the changes.", "ref": f"adm-{r.status_code}"})
    print(f"[admin] {admin['id']} updated {user_id}: {sorted(changes)}")
    merged = {**current, **changes}
    result = {"razorpay_updated": None, "auth_updated": None}

    # Razorpay keeps its own copy of the customer, used on its receipts and emails.
    cid = current.get("razorpay_customer_id")
    if cid and config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET:
        payload = {k: v for k, v in {"name": changes.get("full_name"),
                                     "contact": f"+91{changes['phone']}" if changes.get("phone") else None}.items() if v}
        try:
            rr = requests.put(f"{billing.RZP}/customers/{cid}", json=payload, timeout=20,
                              auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
            result["razorpay_updated"] = rr.status_code < 300
        except requests.RequestException:
            result["razorpay_updated"] = False

    # Keep the name stored with the login in step, so it isn't re-copied over the correction later.
    if changes.get("full_name"):
        try:
            h = auth._service_headers(); base = f"{config.SUPABASE_URL}/auth/v1/admin/users/{user_id}"
            g = requests.get(base, headers=h, timeout=10)
            meta = (g.json().get("user_metadata") or {}) if g.status_code == 200 else {}
            pr = requests.put(base, headers=h, json={"user_metadata": {**meta, "full_name": changes["full_name"]}}, timeout=10)
            result["auth_updated"] = g.status_code == 200 and pr.status_code < 300
        except requests.RequestException:
            result["auth_updated"] = False
    merged["status"] = status_of(merged)
    return {"user": merged, "changed": sorted(changes), **result}
