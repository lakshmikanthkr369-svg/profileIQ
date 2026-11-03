"""Verifies the Supabase login token sent by the browser and loads the user's profile."""
import hashlib
import time
from datetime import datetime, timezone

import requests
from fastapi import Header, HTTPException

from . import config

_TOKEN_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_SECONDS = 60


def _service_headers():
    return {"apikey": config.SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json"}


def verify_token(token: str) -> dict:
    """Asks Supabase who this token belongs to. Returns {"id", "email"} or raises 401."""
    key = hashlib.sha256(token.encode()).hexdigest()
    hit = _TOKEN_CACHE.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    try:
        r = requests.get(f"{config.SUPABASE_URL}/auth/v1/user",
                         headers={"apikey": config.SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"}, timeout=10)
    except requests.RequestException:
        raise HTTPException(503, {"message": "Login service is unreachable. Please try again.", "ref": "auth-unreachable"})
    if r.status_code != 200:
        raise HTTPException(401, {"message": "Please sign in again.", "ref": "auth-invalid"})
    u = r.json()
    meta = u.get("user_metadata") or {}
    user = {"id": u.get("id"), "email": u.get("email"),
            "full_name": (meta.get("full_name") or "").strip(), "mobile": (meta.get("mobile") or "").strip()}
    if not user["id"]:
        raise HTTPException(401, {"message": "Please sign in again.", "ref": "auth-invalid"})
    if len(_TOKEN_CACHE) > 5000:
        _TOKEN_CACHE.clear()
    _TOKEN_CACHE[key] = (time.time() + _CACHE_SECONDS, user)
    return user


def current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, {"message": "Please sign in.", "ref": "auth-missing"})
    return verify_token(authorization[7:].strip())


# ── profile helpers (service key: the server decides plan and scan limits, never the browser) ──
def get_profile(user_id: str) -> dict | None:
    r = requests.get(f"{config.SUPABASE_URL}/rest/v1/profiles", params={"id": f"eq.{user_id}", "select": "*"},
                     headers=_service_headers(), timeout=10)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
    if not isinstance(data, list):
        print(f"[profile] could not load profile (HTTP {r.status_code})")
        return None
    return data[0] if data else None


def is_pro(profile: dict | None) -> bool:
    if not profile or profile.get("plan") != "pro":
        return False
    expires = profile.get("pro_expires_at")
    if not expires:
        return False
    return datetime.fromisoformat(expires.replace("Z", "+00:00")) > datetime.now(timezone.utc)


def reset_scans_if_needed(profile: dict) -> dict:
    reset_date = profile.get("scans_reset_date")
    if reset_date:
        rd = datetime.fromisoformat(reset_date)
        now = datetime.now(timezone.utc).date()
        if (now - rd.date()).days >= 30:
            requests.patch(f"{config.SUPABASE_URL}/rest/v1/profiles", params={"id": f"eq.{profile['id']}"},
                           headers={**_service_headers(), "Prefer": "return=minimal"},
                           json={"scans_used": 0, "scans_reset_date": str(now)}, timeout=10)
            profile["scans_used"] = 0
    return profile


def free_scans_left(profile: dict | None) -> int:
    if not profile:
        return 0
    return max(0, config.FREE_SCANS_PER_MONTH - int(profile.get("scans_used") or 0))


def record_scan(profile: dict) -> int:
    """Counts one scan. The update only applies if the stored count is still what we read, so two
    parallel requests cannot both use the last free scan. Returns the new count."""
    used = int(profile.get("scans_used") or 0)
    r = requests.patch(f"{config.SUPABASE_URL}/rest/v1/profiles",
                       params={"id": f"eq.{profile['id']}", "scans_used": f"eq.{used}"},
                       headers={**_service_headers(), "Prefer": "return=representation"},
                       json={"scans_used": used + 1}, timeout=10)
    if r.status_code in (200, 201) and r.json():
        return used + 1
    return used


def sync_profile_details(user: dict, profile: dict | None) -> dict | None:
    """Copies the name, email and mobile given at sign-up (kept by Supabase with the login) onto the
    profile, filling only blanks. Runs for the signed-in user only, using details Supabase itself holds,
    so nobody can write details for someone else. Creates the profile row if it is missing."""
    want = {"email": user.get("email"), "full_name": user.get("full_name"), "phone": user.get("mobile")}
    want = {k: v for k, v in want.items() if v}
    if profile is None:
        base = {"id": user["id"], "plan": "free", "scans_used": 0, **want}
        r = requests.post(f"{config.SUPABASE_URL}/rest/v1/profiles",
                          headers={**_service_headers(), "Prefer": "return=representation,resolution=merge-duplicates"},
                          json=base, timeout=10)
        if r.status_code in (200, 201) and r.json():
            return r.json()[0]
        print(f"[profile] could not create profile (HTTP {r.status_code})")
        return None
    fill = {k: v for k, v in want.items() if not (profile.get(k) or "").strip()}
    if fill:
        r = requests.patch(f"{config.SUPABASE_URL}/rest/v1/profiles", params={"id": f"eq.{user['id']}"},
                           headers={**_service_headers(), "Prefer": "return=minimal"}, json=fill, timeout=10)
        if r.status_code in (200, 204):
            profile = {**profile, **fill}
        else:
            print(f"[profile] could not fill details (HTTP {r.status_code})")
    return profile
