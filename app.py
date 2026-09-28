import streamlit as st
import streamlit.components.v1 as components
import anthropic
import pdfplumber
import os
import json
import re
import time
import requests
import razorpay
from io import BytesIO
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

load_dotenv()
try:
    API_KEY = st.secrets["ANTHROPIC_API_KEY"]
except:
    API_KEY = os.getenv("ANTHROPIC_API_KEY")

try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://adybtayirxocljwkydyg.supabase.co")
except:
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://adybtayirxocljwkydyg.supabase.co")

try:
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except:
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFkeWJ0YXlpcnhvY2xqd2t5ZHlnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NDEzMTM4MCwiZXhwIjoyMDk5NzA3MzgwfQ.sW_EkD71c8jJP1XM35PH5MYAkK8S0ThJlgQwe94hA_E")

# Anon key for auth endpoints (login/register/reset)
# Service role key bypasses RLS but auth endpoints need anon key
try:
    SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
except:
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFkeWJ0YXlpcnhvY2xqd2t5ZHlnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQxMzEzODAsImV4cCI6MjA5OTcwNzM4MH0.8ZHHN1P6x38XdXVLNatdAHDG7FOGNquL-7CwGFegNXU")

# ── Razorpay (subscriptions) ──
try:
    RAZORPAY_KEY_ID = st.secrets["RAZORPAY_KEY_ID"]
except:
    RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")

try:
    RAZORPAY_KEY_SECRET = st.secrets["RAZORPAY_KEY_SECRET"]
except:
    RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

try:
    RAZORPAY_PLAN_ID = st.secrets["RAZORPAY_PLAN_ID"]
except:
    RAZORPAY_PLAN_ID = os.getenv("RAZORPAY_PLAN_ID", "")

razorpay_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

st.set_page_config(page_title="ProfileIQ — AI Resume Intelligence", page_icon="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAEAElEQVR4nO1bW0gUUQA99zqru46WJlHpZlgYEb0p6SdJrAgK7KvoI3pAReVHfQQRFBHRTxT9JBSUfRREfYhlfRSBVBQW9rCInq49pEKt1WadXXd2po8wd5xpZrcuc/cx529m7+ycc+65b4YgCYTOiVoy5XlB3BIiiZa1LZguov8GOzOo1Y/pLh6w12DqTiYIN4NZGgwJyFTxgLk2alcg0zBao2UfkA34Y0A21P4w4rXS0TeyBcOa3SbAmwBvkGyMfzyyPgGuAbwJ8IZrAG8CvOEawJsAb7gG8CbAG1lvgMDqj/Y3+XClPVd37+zGEKorFcvnAr0U15978DAgoKuPIjhIoGoERfkq/MUaFk5RsHJWFLNKY6yo6sDMgGTRLxMcuubDjeceqCarkW8DFN8GgPYPOTh9Jw9LKhUcqZNRWqQy5cGlCXT1UdQ1FKClw1y8Ge6+FVDXUICnn3KYcnE8AVKEYPsFEd0/9N7P8cewuzaMeZNjyKHAi+4cnGrNw/33IxSDgwQ7L4po2ilhwhg2SXA8AQ2teejs0b+2qkLBpa0SllQqKPRqyM/VUFWhoHFTCCtmRnVleySCYze9zPg4aoAUIbjQpu8oKQGOrpHhMUk2JcDhOhm+XH07aenwoDvIhrqjBrQFBMhD+rOJqgoFU0r+HucSUUPtDP1IElOBe+/YtF5HDWj/YKzmBeX2w9v8cuNQ+vgjm87QUQP6JONJXFkCw5q/yDhU9Elp2AR+ho0GeD3246BZmX454RNwSzhqQIHXKCQctRdiViYR4xKBowaUFBhJf+m3p/A5aDRg0tg0nAfMn2zs8J59tu/Mnnw09vizy9isDRw1YPFUxRDdB52CZQq+hwhuv9IbQAmwfKb1IitROGrAGK+G9YuGdPeUGHCw2YeYSaJVDTjQ7DPMHVbPiWJiuk6Fd9VEUD5OT771jYCNjSIedAoIRQjkIYJHXQI2nxdx86VHV3acqGHfSpkZH8cXQ2N9Gs5sCGFTo4ivAyP+twUEtAWs6RR6fz87vpDdaR6X5fC08Squ1ktYNTsKmuBwvqA8hqYdEub62W6McNsQKc7XcHLdIHYvo7je4cHDLgGBXoqgTAxtfq4/hktbJRA2cx8dUvJ0uPvH7w2T+Nne3hVhbKuOMH9XSm6KlhWrOLF2UNc8jt/yovU1+8CmpAEAUF2poL4m/Oda1YA9l/MNmyn/i5Q1AADqayJYOn1kwjO8nTZgsqj6V6RkH+AkUjoBTsA1gDcB3nAN4E2AN1wDeBPgDZrMB0aZBnFLiLgJ4E2ANyiQ3Hd2mYJhzXT0jWxAvFa3CcRfZEMKRms0JCCTTTDTZik2U/YKrCrVsg/IhDTYaUhKYLokIpmK+wUtEk0YSE4haAAAAABJRU5ErkJggg==", layout="wide")

# Inject custom favicon
st.markdown(f"""
<link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAEAElEQVR4nO1bW0gUUQA99zqru46WJlHpZlgYEb0p6SdJrAgK7KvoI3pAReVHfQQRFBHRTxT9JBSUfRREfYhlfRSBVBQW9rCInq49pEKt1WadXXd2po8wd5xpZrcuc/cx529m7+ycc+65b4YgCYTOiVoy5XlB3BIiiZa1LZguov8GOzOo1Y/pLh6w12DqTiYIN4NZGgwJyFTxgLk2alcg0zBao2UfkA34Y0A21P4w4rXS0TeyBcOa3SbAmwBvkGyMfzyyPgGuAbwJ8IZrAG8CvOEawJsAb7gG8CbAG1lvgMDqj/Y3+XClPVd37+zGEKorFcvnAr0U15978DAgoKuPIjhIoGoERfkq/MUaFk5RsHJWFLNKY6yo6sDMgGTRLxMcuubDjeceqCarkW8DFN8GgPYPOTh9Jw9LKhUcqZNRWqQy5cGlCXT1UdQ1FKClw1y8Ge6+FVDXUICnn3KYcnE8AVKEYPsFEd0/9N7P8cewuzaMeZNjyKHAi+4cnGrNw/33IxSDgwQ7L4po2ilhwhg2SXA8AQ2teejs0b+2qkLBpa0SllQqKPRqyM/VUFWhoHFTCCtmRnVleySCYze9zPg4aoAUIbjQpu8oKQGOrpHhMUk2JcDhOhm+XH07aenwoDvIhrqjBrQFBMhD+rOJqgoFU0r+HucSUUPtDP1IElOBe+/YtF5HDWj/YKzmBeX2w9v8cuNQ+vgjm87QUQP6JONJXFkCw5q/yDhU9Elp2AR+ho0GeD3246BZmX454RNwSzhqQIHXKCQctRdiViYR4xKBowaUFBhJf+m3p/A5aDRg0tg0nAfMn2zs8J59tu/Mnnw09vizy9isDRw1YPFUxRDdB52CZQq+hwhuv9IbQAmwfKb1IitROGrAGK+G9YuGdPeUGHCw2YeYSaJVDTjQ7DPMHVbPiWJiuk6Fd9VEUD5OT771jYCNjSIedAoIRQjkIYJHXQI2nxdx86VHV3acqGHfSpkZH8cXQ2N9Gs5sCGFTo4ivAyP+twUEtAWs6RR6fz87vpDdaR6X5fC08Squ1ktYNTsKmuBwvqA8hqYdEub62W6McNsQKc7XcHLdIHYvo7je4cHDLgGBXoqgTAxtfq4/hktbJRA2cx8dUvJ0uPvH7w2T+Nne3hVhbKuOMH9XSm6KlhWrOLF2UNc8jt/yovU1+8CmpAEAUF2poL4m/Oda1YA9l/MNmyn/i5Q1AADqayJYOn1kwjO8nTZgsqj6V6RkH+AkUjoBTsA1gDcB3nAN4E2AN1wDeBPgDZrMB0aZBnFLiLgJ4E2ANyiQ3Hd2mYJhzXT0jWxAvFa3CcRfZEMKRms0JCCTTTDTZik2U/YKrCrVsg/IhDTYaUhKYLokIpmK+wUtEk0YSE4haAAAAABJRU5ErkJggg==">
<link rel="shortcut icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAEAElEQVR4nO1bW0gUUQA99zqru46WJlHpZlgYEb0p6SdJrAgK7KvoI3pAReVHfQQRFBHRTxT9JBSUfRREfYhlfRSBVBQW9rCInq49pEKt1WadXXd2po8wd5xpZrcuc/cx529m7+ycc+65b4YgCYTOiVoy5XlB3BIiiZa1LZguov8GOzOo1Y/pLh6w12DqTiYIN4NZGgwJyFTxgLk2alcg0zBao2UfkA34Y0A21P4w4rXS0TeyBcOa3SbAmwBvkGyMfzyyPgGuAbwJ8IZrAG8CvOEawJsAb7gG8CbAG1lvgMDqj/Y3+XClPVd37+zGEKorFcvnAr0U15978DAgoKuPIjhIoGoERfkq/MUaFk5RsHJWFLNKY6yo6sDMgGTRLxMcuubDjeceqCarkW8DFN8GgPYPOTh9Jw9LKhUcqZNRWqQy5cGlCXT1UdQ1FKClw1y8Ge6+FVDXUICnn3KYcnE8AVKEYPsFEd0/9N7P8cewuzaMeZNjyKHAi+4cnGrNw/33IxSDgwQ7L4po2ilhwhg2SXA8AQ2teejs0b+2qkLBpa0SllQqKPRqyM/VUFWhoHFTCCtmRnVleySCYze9zPg4aoAUIbjQpu8oKQGOrpHhMUk2JcDhOhm+XH07aenwoDvIhrqjBrQFBMhD+rOJqgoFU0r+HucSUUPtDP1IElOBe+/YtF5HDWj/YKzmBeX2w9v8cuNQ+vgjm87QUQP6JONJXFkCw5q/yDhU9Elp2AR+ho0GeD3246BZmX454RNwSzhqQIHXKCQctRdiViYR4xKBowaUFBhJf+m3p/A5aDRg0tg0nAfMn2zs8J59tu/Mnnw09vizy9isDRw1YPFUxRDdB52CZQq+hwhuv9IbQAmwfKb1IitROGrAGK+G9YuGdPeUGHCw2YeYSaJVDTjQ7DPMHVbPiWJiuk6Fd9VEUD5OT771jYCNjSIedAoIRQjkIYJHXQI2nxdx86VHV3acqGHfSpkZH8cXQ2N9Gs5sCGFTo4ivAyP+twUEtAWs6RR6fz87vpDdaR6X5fC08Squ1ktYNTsKmuBwvqA8hqYdEub62W6McNsQKc7XcHLdIHYvo7je4cHDLgGBXoqgTAxtfq4/hktbJRA2cx8dUvJ0uPvH7w2T+Nne3hVhbKuOMH9XSm6KlhWrOLF2UNc8jt/yovU1+8CmpAEAUF2poL4m/Oda1YA9l/MNmyn/i5Q1AADqayJYOn1kwjO8nTZgsqj6V6RkH+AkUjoBTsA1gDcB3nAN4E2AN1wDeBPgDZrMB0aZBnFLiLgJ4E2ANyiQ3Hd2mYJhzXT0jWxAvFa3CcRfZEMKRms0JCCTTTDTZik2U/YKrCrVsg/IhDTYaUhKYLokIpmK+wUtEk0YSE4haAAAAABJRU5ErkJggg==">
""", unsafe_allow_html=True)

# ── SESSION STATE (must be before any widget) ──
defaults = {
    "last_analyzed_file": None, "last_analyzed_jd": None,
    "last_rewritten_file": None, "last_rewritten_jd": None,
    "analysis_result": None,
    "rewrite_data": None, "docx_bytes": None, "pdf_bytes": None,
    "after_score": None, "after_matched": [], "after_missing": [],
    "processing": False,
    # Auth
    "user": None,
    "access_token": None,
    "profile": None,
    "auth_view": "login",  # login | register | forgot
    "show_support": False,
    "pending_subscription_id": None,
    "subscription_error": None,
    "show_manage_sub": False,
    "confirm_cancel_sub": False,
    "is_fresher_mode": False,
    "fresher_loaded": False,
    "fresher_projects": [{"name": "", "description": ""}],
    "fresher_certifications": [{"name": ""}],
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════
# SUPABASE AUTH HELPERS
# ══════════════════════════════════════

def sb_headers(token=None, use_anon=False):
    key = SUPABASE_ANON_KEY if use_anon else SUPABASE_KEY
    h = {"apikey": key, "Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    else:
        h["Authorization"] = f"Bearer {key}"
    return h

def normalize_indian_mobile(raw):
    """Accepts 9876543210, +91 98765 43210, 91-9876543210, 09876543210 etc.
    Returns '+91XXXXXXXXXX' if valid, else None."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return "+91" + digits
    return None

def is_valid_email(e):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$", (e or "").strip()))

def sb_register(email, password):
    r = requests.post(f"{SUPABASE_URL}/auth/v1/signup",
        headers=sb_headers(use_anon=True),
        json={"email": email, "password": password})
    return r.json()

def sb_login(email, password):
    r = requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers=sb_headers(use_anon=True),
        json={"email": email, "password": password})
    return r.json()

def sb_forgot_password(email):
    # Validate email format first
    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        return 'invalid'
    r = requests.post(f"{SUPABASE_URL}/auth/v1/recover",
        headers=sb_headers(use_anon=True),
        json={"email": email,
              "redirect_to": "https://profileiq.co.in/app.html"})
    # Supabase returns 200 even for unknown emails (security by design)
    # We return True so user always sees success (prevents email enumeration)
    return 'sent' if r.status_code == 200 else 'error'

def sb_get_profile(token, user_id):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}&select=*",
        headers=sb_headers(token))
    data = r.json()
    return data[0] if data else None

def sb_increment_scan(token, user_id, current_used):
    requests.patch(f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}",
        headers={**sb_headers(token), "Prefer": "return=minimal"},
        json={"scans_used": current_used + 1})

def sb_reset_scans_if_needed(token, user_id, profile):
    reset_date = profile.get("scans_reset_date")
    if reset_date:
        rd = datetime.fromisoformat(reset_date)
        now = datetime.now(timezone.utc).date()
        if (now - rd.date()).days >= 30:
            requests.patch(f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}",
                headers={**sb_headers(token), "Prefer": "return=minimal"},
                json={"scans_used": 0, "scans_reset_date": str(now)})
            profile["scans_used"] = 0
    return profile

def sb_save_fresher_profile(token, user_id, data):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}",
        headers={**sb_headers(token), "Prefer": "return=minimal"},
        json={"fresher_profile": data})
    return r.status_code in (200, 204)

def sb_submit_support(email, ticket_type, message):
    # Save to Supabase
    r = requests.post(f"{SUPABASE_URL}/rest/v1/support_tickets",
        headers={**sb_headers(), "Prefer": "return=minimal"},
        json={"user_email": email, "type": ticket_type, "message": message})
    saved = r.status_code in [200, 201]
    
    # Send email notification via Resend
    try:
        try:
            RESEND_KEY = st.secrets["RESEND_API_KEY"]
        except Exception:
            RESEND_KEY = os.getenv("RESEND_API_KEY", "")
        if RESEND_KEY:
            resp = requests.post("https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"},
                json={
                    "from": "ProfileIQ <noreply@profileiq.co.in>",
                    "to": ["support@profileiq.co.in"],
                    "subject": f"[ProfileIQ Support] {ticket_type} from {email}",
                    "html": f"<p><b>From:</b> {email}</p><p><b>Type:</b> {ticket_type}</p><p><b>Message:</b><br>{message}</p>"
                })
            if resp.status_code not in (200, 201):
                print(f"[support email] Resend API error {resp.status_code}: {resp.text}")
        else:
            print("[support email] RESEND_API_KEY is not set — skipped sending notification email")
    except Exception as e:
        print(f"[support email] Exception while sending: {e}")
    return saved

def create_pro_subscription(user_id, email):
    """Creates a Razorpay subscription for this user and returns its ID.
    notes.user_id is how the webhook later matches the payment back to
    this Supabase profile — no manual email matching needed."""
    if not razorpay_client or not RAZORPAY_PLAN_ID:
        return None, "Payments are not configured yet. Please contact support."
    try:
        sub = razorpay_client.subscription.create({
            "plan_id": RAZORPAY_PLAN_ID,
            "customer_notify": 1,
            "total_count": 120,  # effectively "until cancelled" (10 years of monthly cycles)
            "notes": {"user_id": user_id, "email": email},
        })
        return sub["id"], None
    except Exception as e:
        return None, str(e)

def reconcile_subscription(subscription_id, user_id):
    """Fallback for when the webhook is slow, misconfigured, or hasn't
    fired at all yet. Asks Razorpay directly for the subscription's real
    status and, if it's already paid, updates Supabase itself. Safe to
    call repeatedly — it's just a read + idempotent write.
    Returns: "paid" | "pending" | "not_paid" | None (on lookup failure)."""
    if not razorpay_client or not subscription_id:
        return None
    try:
        sub = razorpay_client.subscription.fetch(subscription_id)
    except Exception:
        return None

    status = sub.get("status")
    if status in ("active", "charged"):
        current_end = sub.get("current_end")
        if current_end:
            expires_at = (
                datetime.fromtimestamp(current_end, tz=timezone.utc) + timedelta(hours=6)
            ).isoformat()
        else:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=31)).isoformat()
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}",
            headers={**sb_headers(), "Prefer": "return=minimal"},
            json={
                "plan": "pro",
                "pro_expires_at": expires_at,
                "razorpay_subscription_id": subscription_id,
                "razorpay_customer_id": sub.get("customer_id"),
                "subscription_status": status,
            },
        )
        return "paid"

    if status in ("created", "authenticated", "pending"):
        return "pending"

    return "not_paid"  # halted / cancelled / completed / expired

def render_razorpay_checkout(subscription_id, email, key_suffix=""):
    """Embeds Razorpay Checkout and auto-opens it for the given subscription."""
    components.html(f"""
    <div id="rzp-status-{key_suffix}" style="font-family:Inter,sans-serif;font-size:13px;color:#888;padding:8px 0">
      Opening secure checkout...
    </div>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <script>
    (function() {{
        var status = document.getElementById("rzp-status-{key_suffix}");
        var options = {{
            "key": "{RAZORPAY_KEY_ID}",
            "subscription_id": "{subscription_id}",
            "name": "ProfileIQ",
            "description": "ProfileIQ Pro — monthly subscription",
            "prefill": {{ "email": "{email}" }},
            "theme": {{ "color": "#F59E0B" }},
            "config": {{
                "display": {{
                    "blocks": {{
                        "upi": {{
                            "name": "Pay via UPI",
                            "instruments": [{{ "method": "upi" }}]
                        }}
                    }},
                    "sequence": ["block.upi"],
                    "preferences": {{ "show_default_blocks": false }}
                }}
            }},
            "handler": function (response) {{
                status.innerHTML = "&#9989; Payment successful! It can take a few seconds to activate. Click <b>Refresh my Pro status</b> below.";
                status.style.color = "#22c55e";
            }},
            "modal": {{
                "ondismiss": function() {{
                    status.innerHTML = "Checkout closed. Click Upgrade to Pro again if you'd like to retry.";
                }}
            }}
        }};
        var rzp = new Razorpay(options);
        rzp.on('payment.failed', function (response) {{
            status.innerHTML = "&#10060; Payment failed: " + response.error.description;
            status.style.color = "#f87171";
        }});
        rzp.open();
    }})();
    </script>
    """, height=650, scrolling=True)

def render_upgrade_cta(key_suffix):
    """Renders the Upgrade to Pro button + checkout flow. Call once per
    location in the page where an upgrade CTA is needed."""
    if st.session_state.pending_subscription_id:
        sub_id = st.session_state.pending_subscription_id
        # Don't blindly reopen checkout — check with Razorpay first. If this
        # subscription was already paid (e.g. webhook hasn't updated
        # Supabase yet), reopening checkout just shows a stale "already
        # completed" screen. Reconcile and clear it instead.
        with st.spinner("Checking payment status..."):
            result = reconcile_subscription(sub_id, st.session_state.user["id"])
        if result == "paid":
            fresh_profile = sb_get_profile(st.session_state.access_token, st.session_state.user["id"])
            if fresh_profile:
                st.session_state.profile = fresh_profile
            st.session_state.pending_subscription_id = None
            st.success("✅ Payment confirmed — you're Pro now!")
            st.rerun()
        elif result == "not_paid":
            # Subscription was cancelled/halted/expired before completing —
            # clear it so the next click creates a fresh one.
            st.session_state.pending_subscription_id = None
            st.session_state.subscription_error = "That checkout session ended without payment. Please try again."
            st.rerun()
        else:
            render_razorpay_checkout(sub_id, user_email, key_suffix=key_suffix)

        cols = st.columns([1, 1])
        with cols[0]:
            if st.button("Refresh my Pro status", use_container_width=True, key=f"btn_refresh_{key_suffix}"):
                with st.spinner("Refreshing your status..."):
                    reconcile_subscription(st.session_state.pending_subscription_id, st.session_state.user["id"])
                    fresh_profile = sb_get_profile(st.session_state.access_token, st.session_state.user["id"])
                if fresh_profile:
                    st.session_state.profile = fresh_profile
                if is_pro(fresh_profile or {}):
                    st.session_state.pending_subscription_id = None
                st.rerun()
        with cols[1]:
            if st.button("Cancel checkout", use_container_width=True, key=f"btn_cancel_checkout_{key_suffix}"):
                st.session_state.pending_subscription_id = None
                st.rerun()
    else:
        if st.session_state.subscription_error:
            st.markdown(f'<div class="warn-badge">⚠️ {st.session_state.subscription_error}</div>', unsafe_allow_html=True)
        if st.button("Upgrade to Pro — Rs.199/month", use_container_width=True, type="primary", key=f"btn_upgrade_{key_suffix}"):
            with st.spinner("Setting up secure checkout..."):
                sub_id, err = create_pro_subscription(st.session_state.user["id"], user_email)
            if err:
                st.session_state.subscription_error = err
            else:
                st.session_state.subscription_error = None
                st.session_state.pending_subscription_id = sub_id
            st.rerun()

def cancel_subscription(subscription_id, user_id):
    """Cancels at the end of the current billing cycle — the user keeps
    Pro access until pro_expires_at, matching the refund policy (no
    immediate loss of access on cancellation)."""
    if not razorpay_client or not subscription_id:
        return False, "Payments are not configured."
    try:
        razorpay_client.subscription.cancel(subscription_id, {"cancel_at_cycle_end": True})
    except Exception as e:
        return False, str(e)
    # Reflect this immediately in Supabase rather than waiting for the
    # webhook, so the UI can show "cancels on <date>" right away.
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}",
        headers={**sb_headers(), "Prefer": "return=minimal"},
        json={"subscription_status": "cancel_at_cycle_end"},
    )
    return True, None

# ── Invoices: list + re-send ──
INVOICE_FROM = os.getenv("INVOICE_FROM", "ProfileIQ <support@profileiq.co.in>")
INVOICE_REPLY_TO = os.getenv("SUPPORT_EMAIL", "support@profileiq.co.in")
INVOICE_RESEND_COOLDOWN_SECONDS = 60
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_IST = timezone(timedelta(hours=5, minutes=30))  # India has no DST, so a fixed offset is exact

def get_resend_key():
    try:
        return st.secrets["RESEND_API_KEY"]
    except Exception:
        return os.getenv("RESEND_API_KEY", "")

def fmt_inr(paise, currency="INR"):
    sym = "₹" if (currency or "INR") == "INR" else f"{currency} "
    return f"{sym}{(paise or 0) / 100:,.2f}"

def fmt_invoice_date(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(_IST).strftime("%d %b %Y")
    except Exception:
        return str(iso or "")[:10]

def invoice_method_label(m):
    names = {"upi": "UPI Autopay", "card": "Card", "netbanking": "Net banking", "wallet": "Wallet", "emandate": "e-Mandate"}
    return names.get(m or "", (m or "Online payment").upper() if m else "Online payment")

def _pg_error_ref(resp):
    """Short, safe reference for a failed Supabase call: HTTP status + PostgREST code."""
    code = ""
    try:
        code = (resp.json() or {}).get("code") or ""
    except Exception:
        pass
    return f"HTTP {resp.status_code}" + (f" {code}" if code else "")

def sb_list_invoices_ex(user_id, limit=12):
    """Newest first. Returns (rows, error_ref): rows is None on error (so the UI
    can say so) and [] when there are none. ALWAYS filtered by the logged-in
    user's id. Only asks for columns from migration 03, so listing works even
    before migration 04 has been run."""
    if not _UUID_RE.match(str(user_id or "")):
        return None, "bad-user-id"
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/invoices?user_id=eq.{user_id}"
            "&select=id,invoice_number,issued_at,amount_paise,currency,payment_method,emailed_at"
            f"&order=id.desc&limit={limit + 1}",
            headers=sb_headers(), timeout=15)
        if r.status_code != 200:
            ref = _pg_error_ref(r)
            print(f"[invoices] list failed {ref}: {r.text[:300]}")
            if "PGRST205" in ref or "42P01" in ref:
                print("[invoices] *** the invoices table is missing - run 03_invoices_and_phone_migration.sql in Supabase ***")
            elif "42703" in ref:
                print("[invoices] *** a column is missing - run the 03 and 04 migrations in Supabase ***")
            elif r.status_code in (401, 403):
                print("[invoices] *** SUPABASE_KEY was not accepted - check the Railway variable ***")
            return None, ref
        return r.json(), None
    except Exception as e:
        print(f"[invoices] list error: {e}")
        return None, type(e).__name__

def sb_list_invoices(user_id, limit=12):
    return sb_list_invoices_ex(user_id, limit)[0]

def resend_invoice_email(user_id, invoice_id, fallback_email=""):
    """Re-sends the stored invoice to the customer's OWN address (never one
    supplied by the browser). Returns (ok, message)."""
    if not _UUID_RE.match(str(user_id or "")) or not str(invoice_id).isdigit():
        return False, "Invoice not found."
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/invoices?id=eq.{int(invoice_id)}&user_id=eq.{user_id}"
            "&select=id,invoice_number,customer_email,razorpay_payment_id,html_body,text_body,emailed_at,last_resent_at,resend_count&limit=1",
            headers=sb_headers(), timeout=15)
        rows = r.json() if r.status_code == 200 else None
        if rows is None:
            print(f"[invoices] load failed {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[invoices] load error: {e}")
        rows = None
    if rows is None:
        return False, "We couldn't load that invoice right now. Please try again shortly."
    if not rows:
        return False, "Invoice not found."
    inv = rows[0]
    if not inv.get("html_body"):
        return False, "This invoice was created before re-sending was available. Please write to support@profileiq.co.in and we'll send it to you."

    last = inv.get("last_resent_at") or inv.get("emailed_at")
    if last:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(str(last).replace("Z", "+00:00"))).total_seconds()
            if age < INVOICE_RESEND_COOLDOWN_SECONDS:
                return False, "This invoice was emailed less than a minute ago — please check your inbox (and spam folder), or try again shortly."
        except Exception:
            pass

    key = get_resend_key()
    if not key:
        print("[invoices] RESEND_API_KEY is not set - cannot re-send invoice")
        return False, "Email isn't available right now. Please write to support@profileiq.co.in."
    to_addr = inv.get("customer_email") or fallback_email
    if not to_addr:
        return False, "We don't have an email address on file for this invoice. Please write to support@profileiq.co.in."

    payload = {"from": INVOICE_FROM, "to": [to_addr], "reply_to": INVOICE_REPLY_TO,
               "subject": f"Your ProfileIQ invoice {inv['invoice_number']} (copy)", "html": inv["html_body"]}
    if inv.get("text_body"):
        payload["text"] = inv["text_body"]
    try:
        resp = requests.post("https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     # a new key each minute: Resend caches responses per key, so a fixed one would
                     # silently swallow every later re-send
                     "Idempotency-Key": f"invoice-{inv['razorpay_payment_id']}-resend-{int(time.time() // 60)}"},
            json=payload, timeout=20)
    except Exception as e:
        print(f"[invoices] resend error: {e}")
        return False, "We couldn't send the email right now. Please try again shortly."
    if resp.status_code not in (200, 201):
        print(f"[invoices] Resend rejected {resp.status_code}: {resp.text[:300]}")
        return False, "We couldn't send the email right now. Please try again shortly."

    now_iso = datetime.now(timezone.utc).isoformat()
    patch = {"last_resent_at": now_iso, "resend_count": int(inv.get("resend_count") or 0) + 1}
    if not inv.get("emailed_at"):
        patch["emailed_at"] = now_iso
    try:
        requests.patch(f"{SUPABASE_URL}/rest/v1/invoices?id=eq.{int(invoice_id)}&user_id=eq.{user_id}",
            headers={**sb_headers(), "Prefer": "return=minimal"}, json=patch, timeout=15)
    except Exception as e:
        print(f"[invoices] could not record re-send: {e}")
    return True, f"Invoice {inv['invoice_number']} sent to {to_addr}. It can take a minute to arrive — check spam if you don't see it."

def render_invoices_panel(user_id, fallback_email):
    from html import escape as _e
    st.markdown("<div style='font-size:11px;font-weight:700;color:#888;letter-spacing:0.12em;margin:18px 0 6px'>🧾 INVOICES</div>", unsafe_allow_html=True)
    cache = st.session_state.get("invoices_cache")
    if not cache or cache.get("uid") != user_id or time.time() - cache.get("ts", 0) > 60:
        with st.spinner("Loading invoices..."):
            rows, err_ref = sb_list_invoices_ex(user_id)
        cache = {"uid": user_id, "ts": time.time(), "rows": rows, "ref": err_ref}
        st.session_state.invoices_cache = cache
    rows = cache["rows"]
    if rows is None:
        st.markdown('<div class="auth-error">⚠️ We couldn\'t load your invoices right now. Please try again in a moment.'
                    f'<br><span style="font-size:11px;opacity:.7">Reference: {_e(str(cache.get("ref") or "unknown"))}</span></div>', unsafe_allow_html=True)
        return
    if not rows:
        st.markdown("<div style='color:#888;font-size:13px'>No invoices yet — your first invoice appears here right after your first payment.</div>", unsafe_allow_html=True)
        return
    flash = st.empty()
    for inv in rows[:12]:
        c1, c2 = st.columns([4.2, 1.8])
        sent = bool(inv.get("emailed_at"))
        with c1:
            status = '<span style="color:#4ade80">Emailed ✓</span>' if sent else '<span style="color:#F59E0B">Email not sent yet</span>'
            st.markdown(
                f'<div style="padding:4px 0;line-height:1.55"><b style="color:#fff">{_e(str(inv.get("invoice_number", "")))}</b>'
                f'<span style="color:#888;font-size:12px"> · {_e(fmt_invoice_date(inv.get("issued_at")))}'
                f' · {_e(fmt_inr(inv.get("amount_paise"), inv.get("currency")))}'
                f' · {_e(invoice_method_label(inv.get("payment_method")))}</span>'
                f'<br><span style="font-size:11px">{status}</span></div>', unsafe_allow_html=True)
        with c2:
            if st.button("Email me" if sent else "Send to my email", use_container_width=True, key=f"inv_resend_{inv['id']}"):
                with st.spinner("Sending..."):
                    ok, msg = resend_invoice_email(user_id, inv["id"], fallback_email)
                st.session_state.invoices_cache = None
                flash.markdown(f'<div class="{"auth-success" if ok else "auth-error"}">{"✓ " if ok else "⚠️ "}{_e(msg)}</div>', unsafe_allow_html=True)
    if len(rows) > 12:
        st.caption("Showing your latest 12 invoices.")

def is_pro(profile):
    if not profile: return False
    if profile.get("plan") != "pro": return False
    expires = profile.get("pro_expires_at")
    if not expires: return False
    exp = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    return exp > datetime.now(timezone.utc)

def free_scans_left(profile):
    if not profile: return 0
    used = profile.get("scans_used", 0)
    return max(0, 3 - used)

def logout():
    st.session_state.user = None
    st.session_state.access_token = None
    st.session_state.profile = None
    st.session_state.analysis_result = None
    st.session_state.rewrite_data = None
    st.session_state.after_score = None
    st.rerun()


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,600;0,700;0,900;1,400&display=swap');
*, html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: #111 !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.5rem 2rem 4rem !important; max-width: 1080px !important; }
/* Fix password toggle visibili text */
button[aria-label="Show password"],
button[aria-label="Hide password"] { display: none !important; }
/* Fix button text wrapping */
.stButton > button { white-space: nowrap !important; }

/* ── GLOBAL FIXES ── */
/* Hide password visibility toggle everywhere */
[data-testid="stPasswordFieldToggle"] { display: none !important; }
/* Hide InputInstructions */
[data-testid="InputInstructions"] { display: none !important; }
/* Fix button text wrapping */
.stButton > button { white-space: nowrap !important; }

/* ── HERO ── */
.hero { display: grid; grid-template-columns: 1.1fr 1fr; border-radius: 16px; overflow: hidden; margin-bottom: 20px; min-height: 250px; }
.hero-left { background: #1a1a1a; padding: 32px 28px; display: flex; flex-direction: column; justify-content: space-between; }
.hero-logo { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.logo-mark { background: #F59E0B; color: #1a1a1a; font-size: 15px; font-weight: 900; width: 42px; height: 42px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.logo-wordmark { font-size: 22px; font-weight: 900; color: #fff; letter-spacing: -0.5px; line-height: 1.1; }
.logo-wordmark span { color: #F59E0B; }
.logo-sub { font-size: 10px; color: #666; text-transform: uppercase; letter-spacing: 0.14em; margin-top: 2px; }
.hero-headline { font-size: 40px; font-weight: 900; color: #fff; line-height: 0.95; letter-spacing: -2px; margin-bottom: 14px; }
.hero-headline em { font-style: normal; color: #F59E0B; }
.hero-body { font-size: 12px; color: #777; line-height: 1.65; margin-bottom: 22px; }
.hero-stats { display: flex; gap: 24px; }
.stat-num { font-size: 20px; font-weight: 900; color: #F59E0B; }
.stat-lbl { font-size: 9px; color: #555; text-transform: uppercase; letter-spacing: 0.08em; }

/* Hero right panel */
.hero-right { background: #fff; padding: 26px 22px; }

/* ── MOBILE RESPONSIVE ── */
@media (max-width: 768px) {
    .block-container { padding: 0.8rem 0.8rem 4rem !important; }
    .hero { grid-template-columns: 1fr !important; }
    .hero-right { display: none !important; }
    .hero-headline { font-size: 28px !important; letter-spacing: -1px !important; }
    .hero-left { padding: 20px 18px !important; }
    .results-wrap { grid-template-columns: 1fr !important; }
    .score-panel { padding: 16px !important; }
    .sp-num { font-size: 48px !important; }
    div[data-testid="stColumns"] { flex-direction: column !important; }
    div[data-testid="stColumns"] > div { width: 100% !important; min-width: 100% !important; }
}

/* ── MID-RANGE (between mobile-stack and full desktop) ──
   Narrow laptop windows/tablets sit in this gap: wide enough that columns
   stay side-by-side, but too narrow for full button labels. Shrink text
   and padding here instead of truncating. */
@media (min-width: 769px) and (max-width: 1100px) {
    .stButton > button {
        font-size: 10px !important;
        padding: 11px 10px !important;
        letter-spacing: 0.03em !important;
    }
}

/* ── UPLOAD — remove inner dark box, fill card width ── */
[data-testid="stFileUploader"] { width: 100% !important; }
[data-testid="stFileUploaderDropzone"] {
    flex-direction: column !important;
    align-items: stretch !important;
    background-color: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 4px 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
[data-testid="stFileUploaderDropzone"] * {
    white-space: normal !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
}
[data-testid="stFileUploaderDropzone"] > div,
[data-testid="stFileUploaderDropzone"] > div > div,
[data-testid="stFileUploaderDropzone"] > div > div > span {
    display: block !important;
    width: 100% !important;
}
/* Upload button - full width amber */
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] {
    width: 100% !important;
    background: #F59E0B !important;
    color: #1a1a1a !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 12px 24px !important;
    font-size: 13px !important;
    font-weight: 800 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    cursor: pointer !important;
    font-family: Inter, sans-serif !important;
    text-align: center !important;
    box-sizing: border-box !important;
    line-height: 1.2 !important;
}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]:hover {
    opacity: 0.88 !important;
}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] [data-testid="stIconMaterial"] {
    display: none !important;
}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] span {
    display: inline !important;
    text-align: center !important;
    font-weight: 800 !important;
    color: #1a1a1a !important;
    line-height: 1.2 !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
    text-align: center !important;
    color: #888 !important;
    font-size: 11px !important;
}
[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-borderlessIcon"] {
    background: transparent !important;
    border: none !important;
    color: #888 !important;
    width: auto !important;
    padding: 4px !important;
}
/* Catch-all: Material icon ligature text (e.g. "add", "close", "delete") can
   render as literal words if the icon font hasn't loaded yet or a new
   Streamlit release adds an icon we haven't manually targeted. Zeroing the
   font-size everywhere is a safe default since every icon spot in this app
   already has its own custom label/graphic. */
[data-testid="stIconMaterial"] { font-size: 0 !important; line-height: 0 !important; }

/* Fix 4: the dropzone was stretching to match the Job Description column's
   height (flex align-items: stretch), so empty space below the button was
   still part of the clickable upload target. Constrain it to its own
   content height so clicks outside the visible button/instructions don't
   trigger the file picker. */
[data-testid="stFileUploader"] {
    align-self: flex-start !important;
    height: auto !important;
    flex: 0 0 auto !important;
}
[data-testid="stFileUploaderDropzone"] {
    align-self: flex-start !important;
    height: auto !important;
    flex-grow: 0 !important;
}

/* ── TEXTAREA — remove resize handle ── */
[data-testid="stTextAreaRootElement"] textarea { resize: none !important; }
[data-testid="InputInstructions"] { display: none !important; }
.panel-title { font-size: 9px; font-weight: 700; color: #bbb; text-transform: uppercase; letter-spacing: 0.14em; border-bottom: 2px solid #1a1a1a; padding-bottom: 7px; margin-bottom: 16px; }
.score-compare { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.sc-box { flex: 1; border-radius: 8px; padding: 12px; text-align: center; }
.sc-box.before-low  { background: #FEF2F2; border: 1px solid #FECACA; }
.sc-box.before-mid  { background: #FFFBEB; border: 1px solid #FDE68A; }
.sc-box.before-high { background: #F0FDF4; border: 1px solid #BBF7D0; }
.sc-box.after-done  { background: #F0FDF4; border: 1px solid #BBF7D0; }
.sc-box.pending { background: #F8F8F8; border: 1px solid #E5E7EB; }
.sc-num { font-size: 30px; font-weight: 900; }
.sc-box.before-low  .sc-num { color: #DC2626; }
.sc-box.before-mid  .sc-num { color: #D97706; }
.sc-box.before-high .sc-num { color: #16A34A; }
.sc-box.after-done  .sc-num { color: #16A34A; }
.sc-box.pending .sc-num { color: #D1D5DB; font-size: 22px; }
.sc-lbl { font-size: 9px; text-transform: uppercase; letter-spacing: 0.07em; color: #bbb; margin-top: 2px; }
.sc-arrow { font-size: 22px; color: #F59E0B; font-weight: 900; }
.kw-cloud { display: flex; flex-wrap: wrap; gap: 5px; }
.kw { font-size: 10px; padding: 3px 9px; border-radius: 4px; font-weight: 600; }
.kw.hit  { background: #F0FDF4; color: #166534; border: 1px solid #BBF7D0; }
.kw.miss { background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA; }
.pending-msg { font-size: 11px; color: #bbb; font-style: italic; text-align: center; padding: 8px 0; }

/* ── INPUT CARDS ── */
.input-card { background: #1a1a1a; border-radius: 10px; padding: 12px 14px 14px; border: 1px solid #2a2a2a; }
.input-card-label { font-size: 11px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }

/* ── TEXTAREA ── */
.stTextArea label { display: none !important; }
.stTextArea > div > div > textarea {
    font-family: 'Inter', sans-serif !important; font-size: 12px !important;
    color: #eee !important; background: #222 !important;
    border: 1.5px solid #333 !important; border-radius: 8px !important;
    padding: 10px 12px !important; min-height: 115px !important;
    resize: none !important;
    box-shadow: none !important;
    outline: none !important;
}
.stTextArea > div > div > textarea:focus { border-color: #F59E0B !important; box-shadow: none !important; }
.stTextArea > div > div > textarea::placeholder { color: #555 !important; }
.stTextArea > div > div { border: none !important; box-shadow: none !important; }

/* ── RADIO AS TABS ── */
div[data-testid="stRadio"] { margin-bottom: 0 !important; }
div[data-testid="stRadio"] > div { gap: 0 !important; flex-wrap: nowrap !important; border-bottom: 2px solid #2a2a2a !important; background: transparent !important; }
div[data-testid="stRadio"] label {
    padding: 11px 26px !important; font-size: 11px !important; font-weight: 800 !important;
    text-transform: uppercase !important; letter-spacing: 0.1em !important;
    color: #555 !important; border-bottom: 3px solid transparent !important;
    margin-bottom: -2px !important; cursor: pointer !important;
    background: none !important; border-radius: 0 !important; transition: color 0.15s !important;
}
div[data-testid="stRadio"] label:has(input:checked) { color: #fff !important; border-bottom-color: #F59E0B !important; }
div[data-testid="stRadio"] label:hover { color: #ddd !important; }
div[data-testid="stRadio"] input { display: none !important; }
div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p { font-size: 11px !important; margin: 0 !important; font-weight: 800 !important; }

/* ── BUTTONS ── */
.stButton > button {
    font-family: 'Inter', sans-serif !important; font-weight: 800 !important;
    font-size: 12px !important; letter-spacing: 0.07em !important;
    text-transform: uppercase !important; border-radius: 8px !important;
    padding: 13px 24px !important; width: 100% !important; transition: opacity 0.15s !important;
    background: #F59E0B !important; color: #1a1a1a !important; border: none !important;
    text-align: center !important; display: flex !important;
    align-items: center !important; justify-content: center !important;
}
.stButton > button p, .stButton > button div, .stButton > button span {
    text-align: center !important; width: auto !important;
    overflow: hidden !important; text-overflow: ellipsis !important; white-space: nowrap !important;
}
.stButton > button { overflow: hidden !important; min-width: 0 !important; }
.stButton > button:hover { opacity: 0.88 !important; }
.stButton > button:disabled { background: #7a5200 !important; color: #333 !important; opacity: 0.5 !important; }
.stButton > button[kind="secondary"] { background: #F59E0B !important; color: #1a1a1a !important; border: none !important; }
.stButton > button[kind="secondary"]:hover { opacity: 0.88 !important; }

/* ── DOWNLOAD BUTTONS ── */
.stDownloadButton > button {
    font-family: 'Inter', sans-serif !important; font-weight: 800 !important;
    font-size: 12px !important; letter-spacing: 0.06em !important;
    text-transform: uppercase !important; border-radius: 8px !important;
    padding: 13px 20px !important; width: 100% !important;
}

/* ── RESULTS ── */
.results-wrap { display: grid; grid-template-columns: 200px 1fr; gap: 14px; margin-bottom: 18px; }
.score-panel { background: #1a1a1a; border-radius: 12px; padding: 24px 16px; text-align: center; border: 1px solid #2a2a2a; }
.sp-label { font-size: 9px; color: #555; text-transform: uppercase; letter-spacing: 0.14em; margin-bottom: 6px; }
.sp-num { font-size: 68px; font-weight: 900; color: #F59E0B; line-height: 1; }
.sp-denom { font-size: 13px; color: #444; margin-bottom: 12px; }
.sp-bar { height: 4px; background: #2a2a2a; border-radius: 2px; margin-bottom: 8px; }
.sp-bar-fill { height: 4px; background: #F59E0B; border-radius: 2px; }
.sp-verdict { font-size: 10px; color: #666; }
.detail-panel { background: #1a1a1a; border-radius: 12px; padding: 20px; border: 1px solid #2a2a2a; }
.dp-section { font-size: 9px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 0.12em; border-bottom: 1px solid #2a2a2a; padding-bottom: 6px; margin-bottom: 10px; margin-top: 16px; }
.dp-section:first-child { margin-top: 0; }
.kw-group { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 2px; }
.suggestions { display: flex; flex-direction: column; gap: 7px; }
.sug-item { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; background: #222; border-radius: 7px; border-left: 3px solid #F59E0B; }
.sug-n { font-size: 10px; font-weight: 900; color: #F59E0B; min-width: 18px; margin-top: 1px; }
.sug-t { font-size: 12px; color: #aaa; line-height: 1.5; }

/* ── DOWNLOAD BAR ── */
.dl-bar { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; }
.dl-bar-title { font-size: 15px; font-weight: 900; color: #fff; margin-bottom: 3px; }
.dl-bar-sub { font-size: 11px; color: #555; margin-bottom: 14px; }

/* ── PREVIEW ── */
.preview-box { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; padding: 24px 28px; margin-top: 4px; }
.preview-name { font-size: 22px; font-weight: 900; color: #fff; margin-bottom: 4px; }
.preview-title { font-size: 13px; color: #F59E0B; font-weight: 600; margin-bottom: 12px; }
.preview-contact { font-size: 11px; color: #666; margin-bottom: 16px; }
.preview-section { font-size: 9px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 0.12em; border-bottom: 1px solid #2a2a2a; padding-bottom: 5px; margin: 16px 0 10px; }
.preview-summary { font-size: 12px; color: #aaa; line-height: 1.7; margin-bottom: 4px; }
.preview-job-title { font-size: 13px; font-weight: 700; color: #fff; margin-bottom: 2px; margin-top: 12px; }
.preview-job-meta { font-size: 11px; color: #F59E0B; margin-bottom: 6px; }
.preview-bullet { font-size: 12px; color: #aaa; line-height: 1.6; padding-left: 14px; position: relative; margin-bottom: 3px; }
.preview-bullet::before { content: "▸"; color: #F59E0B; position: absolute; left: 0; }
.preview-comp-row { font-size: 12px; color: #aaa; margin-bottom: 4px; }
.preview-comp-row b { color: #fff; }

/* ── BADGES ── */
.auth-error { background: #2a1010; border: 1px solid #5a2020; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #f87171; margin-bottom: 12px; }
.auth-success { background: #0a2a1a; border: 1px solid #1a5a30; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #4ade80; margin-bottom: 12px; }
.warn-badge { background: #2a1010; border: 1px solid #5a2020; border-radius: 8px; padding: 10px 14px; font-size: 12px; color: #f87171; margin-bottom: 14px; font-weight: 500; }
.info-badge  { background: #2a2010; border: 1px solid #5a4a10; border-radius: 8px; padding: 10px 14px; font-size: 12px; color: #fbbf24; margin-bottom: 14px; font-weight: 500; }
.stSpinner > div { border-top-color: #F59E0B !important; }
/* ── EXPANDER ── */
[data-testid="stExpander"] {
    border: 1px solid #2a2a2a !important;
    border-radius: 8px !important;
    background: #1a1a1a !important;
}
/* summary = Iy component = <summary> with display:flex */
[data-testid="stExpander"] summary {
    padding: 12px 16px !important;
    list-style: none !important;
    align-items: center !important;
}
[data-testid="stExpander"] summary::-webkit-details-marker { display: none !important; }
/* Hide the material arrow icon text — it renders as stIconMaterial inside summary */
[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
    font-size: 0 !important;
    width: 16px !important;
    height: 16px !important;
    overflow: hidden !important;
    flex-shrink: 0 !important;
}
/* Label text — inside Fy > Zn > p */
[data-testid="stExpander"] summary p {
    color: #aaa !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    margin: 0 !important;
}</style>
""", unsafe_allow_html=True)

# ── HELPERS ──
def get_file_id(f): return f"{f.name}_{f.size}" if f else None

# Model can be switched from Railway (Variables → CLAUDE_MODEL) without a code change,
# e.g. if a model is ever retired.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

def create_json_message(client, **kw):
    """messages.create that never silently returns a half-written JSON answer:
    if the reply was cut off by the token limit, retry once with more room."""
    msg = client.messages.create(**kw)
    if getattr(msg, "stop_reason", None) == "max_tokens":
        bigger = dict(kw, max_tokens=min(int(kw.get("max_tokens", 4096)) * 2, 16000))
        print(f"[ai] answer hit max_tokens={kw.get('max_tokens')} - retrying with {bigger['max_tokens']}")
        msg = client.messages.create(**bigger)
        if getattr(msg, "stop_reason", None) == "max_tokens":
            raise ValueError("ANSWER_TOO_LONG")
    return msg

def describe_ai_error(e):
    """Turns any failure into (friendly message, short reference) for the customer,
    and writes the full detail + traceback to the server log (Railway logs)."""
    import traceback
    name = type(e).__name__
    status = getattr(e, "status_code", None)
    text = str(e)
    low = text.lower()
    print(f"[ai-error] {name} status={status}: {text[:500]}")
    traceback.print_exc()
    busy = "Our AI service is busy right now — please wait a minute and try again."
    generic = "Something went wrong while generating your result. Please try again."
    if isinstance(e, ValueError) and text == "EMPTY_RESUME":
        msg = ("We couldn't read any text from your resume. If it's a scanned image, please upload a "
               "text-based PDF or a Word (.docx) file instead.")
    elif name in ("PackageNotFoundError", "BadZipFile") or "package not found" in low or "not a zip file" in low:
        msg = "We couldn't open that file. Old Word (.doc) files aren't supported — please save it as .docx or PDF and upload again."
    elif "credit balance" in low or "billing" in low or "purchase credits" in low:
        print("[ai-error] *** The Anthropic account is out of credit / billing problem - top up at console.anthropic.com ***")
        msg = "Our AI service is temporarily unavailable. Please try again a little later."
    elif "could not resolve authentication" in low or status in (401, 403):
        print("[ai-error] *** ANTHROPIC_API_KEY is missing, wrong or not allowed - check the Railway variable ***")
        msg = "Our AI service is temporarily unavailable. Please try again a little later."
    elif status == 404 or ("model" in low and "not found" in low):
        print(f"[ai-error] *** Model '{CLAUDE_MODEL}' was not found - set CLAUDE_MODEL in Railway to a current model id ***")
        msg = "Our AI service is temporarily unavailable. Please try again a little later."
    elif status == 429 or "rate" in name.lower() and "limit" in name.lower() or "overloaded" in low or status in (500, 502, 503, 504, 529):
        msg = busy
    elif "timeout" in name.lower() or "timed out" in low:
        msg = "The AI took too long to respond. Please try again."
    elif "APIConnection" in name:
        msg = "We couldn't reach our AI service. Please try again in a moment."
    elif (isinstance(e, ValueError) and text in ("ANSWER_TOO_LONG", "No JSON found")) or "JSONDecodeError" in name:
        msg = "The AI's answer came back incomplete. Please try again."
    else:
        msg = generic
    ref = name + (f" {status}" if status else "")
    return {"message": msg, "ref": ref}

def show_ai_error(ctx):
    """Shows the last AI failure for this screen. It lives in session state so it
    survives the page refresh that follows a failed action (it used to vanish)."""
    err = st.session_state.get("ai_error")
    if err and err.get("ctx") == ctx:
        from html import escape as _e
        st.markdown(f'<div class="auth-error">⚠️ {_e(err["message"])}'
                    f'<br><span style="font-size:11px;opacity:.7">Reference: {_e(err["ref"])}</span></div>', unsafe_allow_html=True)

def extract_text(file):
    name = file.name.lower()
    if name.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            return "\n".join(p.extract_text() for p in pdf.pages if p.extract_text())
    elif name.endswith((".docx", ".doc")):
        doc = DocxDocument(file)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return ""

def score_resume(resume_text, jd):
    """ATS scoring that mirrors how real recruiters and ATS tools score resumes"""
    client = anthropic.Anthropic(api_key=API_KEY)
    msg = client.messages.create(model=CLAUDE_MODEL, max_tokens=1500,
        messages=[{"role":"user","content":f"""You are an ATS (Applicant Tracking System) scoring expert.

Score this resume against the job description the way real ATS tools do:

SCORING RULES:
1. Extract only the TOP 15-20 most important keywords from the JD (core skills, must-have tools, key responsibilities)
2. Do NOT extract every single word — focus on meaningful technical skills, tools, certifications, and key role requirements
3. Match keywords using INTELLIGENT matching — synonyms count, related terms count:
   - "test automation" matches "automation framework", "automated testing"
   - "CI/CD" matches "Jenkins", "GitHub Actions", "pipeline"
   - "Python" matches "Python-based", "Python/Pytest"
   - "QA" matches "quality assurance", "SDET", "test engineer"
4. Calculate score on a REALISTIC scale — a strong relevant resume should score 65-85, not 20-30
5. Formula: score = (matched_count / total_extracted_keywords) * 100

Return in EXACT format — no other text:

ATS_SCORE: [integer between 0-100]
MATCHED_KEYWORDS: [only keywords genuinely present in resume, comma separated]
MISSING_KEYWORDS: [only truly missing important keywords, comma separated, max 8]

Resume:
{resume_text}

Job Description:
{jd}"""}])
    raw = msg.content[0].text.strip()
    result = {"score": 0, "matched": [], "missing": []}
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("ATS_SCORE:"):
            try: result["score"] = int(''.join(c for c in line.split(":",1)[1] if c.isdigit()))
            except: pass
        elif line.startswith("MATCHED_KEYWORDS:"):
            result["matched"] = [k.strip() for k in line.split(":",1)[1].split(",") if k.strip()]
        elif line.startswith("MISSING_KEYWORDS:"):
            result["missing"] = [k.strip() for k in line.split(":",1)[1].split(",") if k.strip()]
    return result

def get_suggestions(resume_text, jd, score, missing_keywords):
    client = anthropic.Anthropic(api_key=API_KEY)

    if score >= 80:
        context = f"""This resume already scores {score}/100 — it's a strong match for the job description.
The candidate has most required keywords. DO NOT suggest adding keywords that are already present.

Focus suggestions ONLY on:
1. How to make the resume stand out beyond ATS — human reviewer appeal
2. Quantifying achievements with specific numbers/metrics if not already done
3. Strengthening the professional summary for impact
4. Interview preparation tips specific to this role
5. Any genuinely missing soft skills or domain knowledge from the JD

Missing keywords (if any): {', '.join(missing_keywords) if missing_keywords else 'None — full match!'}"""
    elif score >= 65:
        context = f"""This resume scores {score}/100 — a decent match but with room to improve.
Missing keywords: {', '.join(missing_keywords[:6]) if missing_keywords else 'None'}

Focus suggestions on:
1. Specific missing keywords to naturally incorporate
2. Bullet points that could be rewritten to better match JD language
3. Strengthening sections that are weak vs the JD requirements
4. Quantifying existing achievements
5. Skills section gaps"""
    else:
        context = f"""This resume scores {score}/100 — significant gaps exist vs the job description.
Missing keywords: {', '.join(missing_keywords[:8]) if missing_keywords else 'None'}

Focus suggestions on:
1. The most critical missing keywords to add immediately
2. Which sections need the most rewriting to match the JD
3. Whether the candidate's experience level matches the role
4. Core skills gaps that need to be addressed
5. Recommend using the AI Rewrite feature"""

    msg = client.messages.create(model=CLAUDE_MODEL, max_tokens=1000,
        messages=[{"role":"user","content":f"""{context}

Give exactly 5 specific, actionable suggestions.
Return ONLY numbered suggestions — no headers, no extra text:
1. [suggestion]
2. [suggestion]
3. [suggestion]
4. [suggestion]
5. [suggestion]

Resume: {resume_text}
Job Description: {jd}"""}])
    sugs = []
    for line in msg.content[0].text.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            s = line.split(".",1)[-1].strip()
            if s: sugs.append(s)
    return sugs

def do_rewrite(resume_text, jd):
    client = anthropic.Anthropic(api_key=API_KEY, timeout=300.0)
    msg = create_json_message(client, model=CLAUDE_MODEL, max_tokens=8192,
        messages=[{"role":"user","content":f"""You are an expert ATS resume optimizer. Your ONLY goal is to maximize the ATS keyword match score between this resume and the job description.

STEP 1 — Extract ALL important keywords from the Job Description:
Skills, tools, technologies, frameworks, methodologies, domain terms, certifications, soft skills.

STEP 2 — Rewrite the resume to include AS MANY of those keywords as possible by:
- Rewriting the Professional Summary to pack in JD keywords naturally
- Rewriting EVERY bullet point to include relevant JD keywords
- Expanding the Skills and Competencies sections with ALL matching JD keywords the candidate could plausibly have based on their experience
- Updating the title/headline to match JD terminology

HARD RULES (never break these):
1. Keep name, email, phone, location, years of experience EXACTLY as they appear
2. Keep job titles, company names, employment dates EXACTLY as they appear
3. Keep education, certifications, languages EXACTLY as they appear
4. Do NOT invent job titles, degrees, or certifications the candidate does not have
5. You MAY add relevant skills to the skills section if they are plausible given the candidate's experience level and domain
6. Rewrite bullets aggressively — every bullet must contain relevant JD keywords
7. The rewritten resume MUST score 80+ on ATS keyword matching

Return ONLY valid JSON — no markdown, no fences, no explanation:
{{"name":"string","title":"string","contact":"string","summary":"string","competencies":[{{"label":"string","value":"string"}}],"experience":[{{"title":"string","company":"string","dates":"string","bullets":["string"]}}],"skills":[{{"label":"string","value":"string"}}],"achievements":["string"],"education":"string","certifications":"string"}}

Resume:
{resume_text}

Job Description:
{jd}"""}])
    raw = msg.content[0].text.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"): raw = part; break
    start = raw.find("{"); end = raw.rfind("}") + 1
    if start == -1 or end <= start: raise ValueError("No JSON found")
    raw = raw[start:end]
    data = json.loads(raw)
    # Sanitize nulls
    def s(v, d): return v if v is not None else d
    data["name"] = s(data.get("name"), "")
    data["title"] = s(data.get("title"), "")
    data["contact"] = s(data.get("contact"), "")
    data["summary"] = s(data.get("summary"), "")
    data["education"] = s(data.get("education"), "")
    data["certifications"] = s(data.get("certifications"), "")
    data["competencies"] = [c for c in s(data.get("competencies"), []) if c and c.get("label") and c.get("value")]
    data["skills"] = [sk for sk in s(data.get("skills"), []) if sk and sk.get("label") and sk.get("value")]
    data["achievements"] = [a for a in s(data.get("achievements"), []) if a]
    cleaned_exp = []
    for job in s(data.get("experience"), []):
        if not job: continue
        cleaned_exp.append({
            "title": s(job.get("title"), ""),
            "company": s(job.get("company"), ""),
            "dates": s(job.get("dates"), ""),
            "bullets": [b for b in s(job.get("bullets"), []) if b]
        })
    data["experience"] = cleaned_exp
    return data

def build_fresher_resume(profile_data, jd):
    """Builds a resume from scratch for a fresher (no prior resume) using
    their education/projects/skills data, tailored to the job description.
    Returns the SAME JSON schema as do_rewrite() so make_docx/make_pdf and
    the preview all work unchanged. Academic projects are mapped into the
    'experience' list but the section is labeled PROJECTS, not WORK
    EXPERIENCE, to stay honest on the actual resume."""
    client = anthropic.Anthropic(api_key=API_KEY, timeout=300.0)

    projects_text = "\n".join(
        f"- {p.get('name','')}: {p.get('description','')}"
        for p in profile_data.get("projects", []) if p.get("name")
    ) or "None provided"
    certs_text = ", ".join(
        c.get("name", "") for c in profile_data.get("certifications", []) if c.get("name")
    ) or "None"

    msg = create_json_message(client, model=CLAUDE_MODEL, max_tokens=8192,
        messages=[{"role": "user", "content": f"""You are an expert resume writer helping a FRESHER (no prior work experience — a student/recent graduate) build their first resume, tailored to a specific job description, optimized for ATS keyword matching.

STEP 1 — Extract important keywords from the Job Description (skills, tools, technologies, frameworks, domain terms).

STEP 2 — Build a resume that naturally incorporates as many relevant keywords as possible by:
- Writing a Professional Summary that frames the candidate's education, skills and projects around the JD's needs
- Rewriting each academic project's description into 2-4 achievement-style bullet points that use relevant JD keywords, WITHOUT inventing outcomes/metrics the candidate didn't provide — infer reasonable, plausible detail from the project description given, don't fabricate specific numbers that weren't implied
- Organizing the skills section to highlight JD-relevant skills first

HARD RULES (never break these):
1. This candidate has NO WORK EXPERIENCE — do not invent jobs, companies, or job titles implying employment
2. Do NOT invent degrees, institutions, or certifications beyond what's given
3. Do NOT fabricate specific metrics/numbers for projects that weren't provided or clearly implied
4. Keep name, email, phone, degree, institute, university, year of passing EXACTLY as given
5. It is fine to include commonly-paired, plausible skills alongside the candidate's stated skills IF clearly appropriate for their stated skill set (e.g. if they list "Python" and the JD wants "REST APIs", it's fine to phrase skills to include API familiarity IF plausible — but never claim a specific certification or tool they never mentioned)

Return ONLY valid JSON — no markdown, no fences, no explanation. Use this EXACT schema:
{{"name":"string","title":"string (a suitable target job title based on the JD)","contact":"string (email | phone)","summary":"string","experience_heading":"PROJECTS","competencies":[{{"label":"string","value":"string"}}],"experience":[{{"title":"string (project name)","company":"Academic Project","dates":"string (leave blank if not known)","bullets":["string"]}}],"skills":[{{"label":"string","value":"string"}}],"achievements":[],"education":"string","certifications":"string"}}

Candidate details:
Name: {profile_data.get('full_name','')}
Email: {profile_data.get('email','')}
Phone: {profile_data.get('phone','')}
Degree: {profile_data.get('degree','')}
Institute: {profile_data.get('institute','')}
University: {profile_data.get('university','')}
Year of Passing: {profile_data.get('year_of_passing','')}
Key Skills: {profile_data.get('key_skills','')}

Academic Projects:
{projects_text}

Certifications: {certs_text}

Job Description:
{jd}"""}])

    raw = msg.content[0].text.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"): raw = part; break
    start = raw.find("{"); end = raw.rfind("}") + 1
    if start == -1 or end <= start: raise ValueError("No JSON found")
    raw = raw[start:end]
    data = json.loads(raw)

    def s(v, d): return v if v is not None else d
    data["name"] = s(data.get("name"), profile_data.get("full_name", ""))
    data["title"] = s(data.get("title"), "")
    data["contact"] = s(data.get("contact"), f"{profile_data.get('email','')} | {profile_data.get('phone','')}")
    data["summary"] = s(data.get("summary"), "")
    data["experience_heading"] = "PROJECTS"
    data["education"] = s(data.get("education"),
        f"{profile_data.get('degree','')}, {profile_data.get('institute','')}, {profile_data.get('university','')} — {profile_data.get('year_of_passing','')}")
    data["certifications"] = s(data.get("certifications"), certs_text if certs_text != "None" else "")
    data["competencies"] = [c for c in s(data.get("competencies"), []) if c and c.get("label") and c.get("value")]
    data["skills"] = [sk for sk in s(data.get("skills"), []) if sk and sk.get("label") and sk.get("value")]
    data["achievements"] = [a for a in s(data.get("achievements"), []) if a]
    cleaned_exp = []
    for proj in s(data.get("experience"), []):
        if not proj: continue
        cleaned_exp.append({
            "title": s(proj.get("title"), ""),
            "company": s(proj.get("company"), "Academic Project"),
            "dates": s(proj.get("dates"), ""),
            "bullets": [b for b in s(proj.get("bullets"), []) if b]
        })
    data["experience"] = cleaned_exp
    return data

# ══════════════════════════════════════
# RESUME TEMPLATES — same data, different look. Switching format re-renders
# instantly from the stored resume data (no extra AI call, no extra cost).
# ══════════════════════════════════════
RESUME_TEMPLATES = {
    "Bold": {
        "label": "Bold — dark header, amber accents",
        "font_docx": "Calibri", "pdf_font": "Helvetica", "pdf_font_bold": "Helvetica-Bold",
        "banner": True, "banner_fill": "1a1a1a",
        "name_color": "FFFFFF", "title_color": "F59E0B", "contact_color": "BBBBBB",
        "name_size": 20, "align": "center",
        "text_color": "1a1a1a", "muted_color": "555555", "company_color": "2E5FA3",
        "sec_color": "1a1a1a", "sec_rule": "F59E0B", "sec_rule_sz": 6, "sec_rule_pdf": 1.5,
        "bullet": "▸", "bullet_color": "F59E0B",
    },
    "Classic": {
        "label": "Classic — serif, traditional black & white",
        "font_docx": "Times New Roman", "pdf_font": "Times-Roman", "pdf_font_bold": "Times-Bold",
        "banner": False, "banner_fill": None,
        "name_color": "000000", "title_color": "333333", "contact_color": "444444",
        "name_size": 22, "align": "center",
        "text_color": "000000", "muted_color": "333333", "company_color": "000000",
        "sec_color": "000000", "sec_rule": "000000", "sec_rule_sz": 6, "sec_rule_pdf": 0.75,
        "bullet": "•", "bullet_color": "000000",
    },
    "Modern": {
        "label": "Modern — navy & blue accents, clean sans-serif",
        "font_docx": "Calibri", "pdf_font": "Helvetica", "pdf_font_bold": "Helvetica-Bold",
        "banner": False, "banner_fill": None,
        "name_color": "1F3A5F", "title_color": "2E5FA3", "contact_color": "555555",
        "name_size": 24, "align": "left",
        "text_color": "222222", "muted_color": "555555", "company_color": "2E5FA3",
        "sec_color": "2E5FA3", "sec_rule": "2E5FA3", "sec_rule_sz": 8, "sec_rule_pdf": 1.5,
        "bullet": "•", "bullet_color": "2E5FA3",
    },
    "Minimal": {
        "label": "Minimal ATS — plain and simple, max compatibility",
        "font_docx": "Arial", "pdf_font": "Helvetica", "pdf_font_bold": "Helvetica-Bold",
        "banner": False, "banner_fill": None,
        "name_color": "000000", "title_color": "000000", "contact_color": "333333",
        "name_size": 18, "align": "left",
        "text_color": "000000", "muted_color": "333333", "company_color": "000000",
        "sec_color": "000000", "sec_rule": None, "sec_rule_sz": 0, "sec_rule_pdf": 0,
        "bullet": "•", "bullet_color": "000000",
    },
}

def _rgb(hexstr):
    return RGBColor(int(hexstr[0:2], 16), int(hexstr[2:4], 16), int(hexstr[4:6], 16))

def make_docx(data, template="Bold"):
    cfg = RESUME_TEMPLATES.get(template) or RESUME_TEMPLATES["Bold"]
    F = cfg["font_docx"]
    doc = DocxDocument()
    for sc in doc.sections:
        sc.top_margin = Inches(0.6); sc.bottom_margin = Inches(0.6)
        sc.left_margin = Inches(0.7); sc.right_margin = Inches(0.7)
    TXT = _rgb(cfg["text_color"]); MUT = _rgb(cfg["muted_color"]); LGR = _rgb("BBBBBB")
    COMPANY = _rgb(cfg["company_color"])
    from docx.oxml.ns import qn; from docx.oxml import OxmlElement
    def shade(p, fill):
        pPr = p._p.get_or_add_pPr(); shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), fill); pPr.append(shd)
    def bdr(p, color, sz):
        pPr = p._p.get_or_add_pPr(); pBdr = OxmlElement('w:pBdr')
        b = OxmlElement('w:bottom'); b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), str(sz))
        b.set(qn('w:space'), '1'); b.set(qn('w:color'), color); pBdr.append(b); pPr.append(pBdr)
    def hp(txt, sz, col, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT, before=0, after=4, sh=None):
        p = doc.add_paragraph(); p.alignment = align
        p.paragraph_format.space_before = Pt(before); p.paragraph_format.space_after = Pt(after)
        r = p.add_run(str(txt or "")); r.bold = bold; r.font.size = Pt(sz); r.font.color.rgb = col; r.font.name = F
        if sh: shade(p, sh)
    def sec(t):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(10); p.paragraph_format.space_after = Pt(4)
        r = p.add_run(str(t)); r.bold = True; r.font.size = Pt(11); r.font.color.rgb = _rgb(cfg["sec_color"]); r.font.name = F
        if cfg["sec_rule"]: bdr(p, cfg["sec_rule"], cfg["sec_rule_sz"])
    def comp(lbl, val):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(str(lbl) + "  "); r1.bold = True; r1.font.color.rgb = TXT; r1.font.size = Pt(10); r1.font.name = F
        r2 = p.add_run(str(val)); r2.font.color.rgb = MUT; r2.font.size = Pt(10); r2.font.name = F
    def bul(txt):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Inches(0.2)
        r1 = p.add_run(cfg["bullet"] + "  "); r1.bold = True; r1.font.color.rgb = _rgb(cfg["bullet_color"]); r1.font.size = Pt(10); r1.font.name = F
        r2 = p.add_run(str(txt)); r2.font.size = Pt(10); r2.font.name = F; r2.font.color.rgb = TXT
    al = WD_ALIGN_PARAGRAPH.CENTER if cfg["align"] == "center" else WD_ALIGN_PARAGRAPH.LEFT
    sh = cfg["banner_fill"] if cfg["banner"] else None
    hp(data.get("name"), cfg["name_size"], _rgb(cfg["name_color"]), bold=True, align=al, after=3, sh=sh)
    hp(data.get("title"), 11, _rgb(cfg["title_color"]), bold=True, align=al, after=3, sh=sh)
    hp(data.get("contact"), 9, _rgb(cfg["contact_color"]), align=al, after=8, sh=sh)
    sec("PROFESSIONAL SUMMARY")
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(4)
    r = p.add_run(str(data.get("summary", ""))); r.font.size = Pt(10); r.font.name = F; r.font.color.rgb = TXT
    if data.get("competencies"):
        sec("CORE COMPETENCIES")
        for c in data["competencies"]: comp(c["label"], c["value"])
    sec(data.get("experience_heading", "WORK EXPERIENCE"))
    for job in data.get("experience", []):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(8); p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(str(job.get("title", ""))); r1.bold = True; r1.font.color.rgb = TXT; r1.font.size = Pt(11); r1.font.name = F
        r2 = p.add_run("  |  "); r2.font.color.rgb = LGR; r2.font.size = Pt(11); r2.font.name = F
        r3 = p.add_run(str(job.get("company", ""))); r3.bold = True; r3.font.color.rgb = COMPANY; r3.font.size = Pt(11); r3.font.name = F
        if job.get("dates"):
            r4 = p.add_run("    " + str(job["dates"])); r4.italic = True; r4.font.color.rgb = MUT; r4.font.size = Pt(10); r4.font.name = F
        for b in job.get("bullets", []): bul(b)
    if data.get("skills"):
        sec("TECHNICAL SKILLS")
        for s in data["skills"]: comp(s["label"], s["value"])
    if data.get("achievements"):
        sec("KEY ACHIEVEMENTS")
        for a in data["achievements"]: bul(a)
    sec("EDUCATION")
    p = doc.add_paragraph(); r = p.add_run(str(data.get("education", ""))); r.font.size = Pt(10); r.font.name = F; r.font.color.rgb = TXT
    if data.get("certifications"):
        sec("CERTIFICATIONS & LANGUAGES")
        p = doc.add_paragraph(); r = p.add_run(str(data["certifications"])); r.font.size = Pt(10); r.font.name = F; r.font.color.rgb = TXT
    buf = BytesIO(); doc.save(buf); buf.seek(0); return buf.read()

def make_pdf(data, template="Bold"):
    from xml.sax.saxutils import escape as _x
    cfg = RESUME_TEMPLATES.get(template) or RESUME_TEMPLATES["Bold"]
    C = lambda h: colors.HexColor("#" + h)
    F, FB = cfg["pdf_font"], cfg["pdf_font_bold"]
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=14*mm, bottomMargin=14*mm, leftMargin=18*mm, rightMargin=18*mm)
    back = C(cfg["banner_fill"]) if cfg["banner"] else None
    align = 1 if cfg["align"] == "center" else 0
    TX, MU, CO = cfg["text_color"], cfg["muted_color"], cfg["company_color"]
    s = getSampleStyleSheet()
    ns = ParagraphStyle("N", parent=s["Normal"], fontSize=cfg["name_size"], textColor=C(cfg["name_color"]), fontName=FB, alignment=align, backColor=back, spaceAfter=2, leading=cfg["name_size"] * 1.3)
    ts = ParagraphStyle("T", parent=s["Normal"], fontSize=11, textColor=C(cfg["title_color"]), fontName=FB, alignment=align, backColor=back, spaceAfter=2, leading=16)
    cs = ParagraphStyle("C", parent=s["Normal"], fontSize=9, textColor=C(cfg["contact_color"]), fontName=F, alignment=align, backColor=back, spaceAfter=10, leading=14)
    ss = ParagraphStyle("S", parent=s["Normal"], fontSize=10, textColor=C(cfg["sec_color"]), fontName=FB, spaceBefore=10, spaceAfter=3, leading=15)
    bs = ParagraphStyle("B", parent=s["Normal"], fontSize=9, textColor=C(MU), fontName=F, spaceBefore=2, spaceAfter=2, leading=13)
    bus = ParagraphStyle("BU", parent=s["Normal"], fontSize=9, textColor=C(TX), fontName=F, spaceBefore=2, spaceAfter=2, leading=13, leftIndent=10)
    bos = ParagraphStyle("BO", parent=s["Normal"], fontSize=9, fontName=F, spaceBefore=2, spaceAfter=2, leading=13)
    story = []
    story.extend([Paragraph(_x(str(data.get("name", ""))), ns), Paragraph(_x(str(data.get("title", ""))), ts), Paragraph(_x(str(data.get("contact", ""))), cs)])
    def sec(t):
        story.append(Paragraph(_x(t), ss))
        if cfg["sec_rule"]: story.append(HRFlowable(width="100%", thickness=cfg["sec_rule_pdf"], color=C(cfg["sec_rule"]), spaceAfter=4))
        else: story.append(Spacer(1, 2))
    def bul(t): story.append(Paragraph(f'<font color="#{cfg["bullet_color"]}"><b>{cfg["bullet"]}</b></font>  {_x(t)}', bus))
    def comp(l, v): story.append(Paragraph(f'<font color="#{TX}"><b>{_x(l)}</b></font>  <font color="#{MU}">{_x(v)}</font>', bos))
    sec("PROFESSIONAL SUMMARY"); story.append(Paragraph(_x(str(data.get("summary", ""))), bs))
    if data.get("competencies"):
        sec("CORE COMPETENCIES")
        for c in data["competencies"]: comp(str(c["label"]), str(c["value"]))
    sec(data.get("experience_heading", "WORK EXPERIENCE"))
    for job in data.get("experience", []):
        story.append(Spacer(1, 4))
        dates = f'<font color="#{MU}"><i>    {_x(str(job["dates"]))}</i></font>' if job.get("dates") else ""
        story.append(Paragraph(
            f'<font color="#{TX}"><b>{_x(str(job.get("title", "")))}</b></font>'
            f'<font color="#bbbbbb">  |  </font>'
            f'<font color="#{CO}"><b>{_x(str(job.get("company", "")))}</b></font>' + dates, bos))
        for b in job.get("bullets", []): bul(str(b))
    if data.get("skills"):
        sec("TECHNICAL SKILLS")
        for sk in data["skills"]: comp(str(sk["label"]), str(sk["value"]))
    if data.get("achievements"):
        sec("KEY ACHIEVEMENTS")
        for a in data["achievements"]: bul(str(a))
    sec("EDUCATION"); story.append(Paragraph(_x(str(data.get("education", ""))), bs))
    if data.get("certifications"):
        sec("CERTIFICATIONS & LANGUAGES"); story.append(Paragraph(_x(str(data["certifications"])), bs))
    doc.build(story); buf.seek(0); return buf.read()

def resume_preview_html(data, tpl):
    """Built-in preview of the chosen format as a white 'paper' card. Needs no
    extra libraries, so a preview is always visible; it mirrors each format's
    fonts, colours and layout (the download uses the exact layout)."""
    from html import escape as _e
    cfg = RESUME_TEMPLATES.get(tpl) or RESUME_TEMPLATES["Bold"]
    fam = cfg["font_docx"]
    # NB: no quote characters here - this value sits inside a single-quoted
    # style='...' attribute, and a stray ' would cut the whole style off.
    ff = ("Times New Roman,Times,serif" if fam == "Times New Roman"
          else "Arial,Helvetica,sans-serif" if fam == "Arial"
          else "Calibri,Carlito,Segoe UI,Helvetica,Arial,sans-serif")
    H = lambda h: "#" + h
    ta = "center" if cfg["align"] == "center" else "left"
    TX, MU, CO = H(cfg["text_color"]), H(cfg["muted_color"]), H(cfg["company_color"])
    P = []
    banner = f"background:{H(cfg['banner_fill'])};padding:10px 8px;" if cfg["banner"] else ""
    P.append(
        f"<div style='{banner}text-align:{ta};margin-bottom:6px'>"
        f"<div style='font-size:{cfg['name_size'] * 0.85:.0f}px;font-weight:800;color:{H(cfg['name_color'])};line-height:1.2'>{_e(str(data.get('name','')))}</div>"
        f"<div style='font-size:10.5px;font-weight:700;color:{H(cfg['title_color'])};margin-top:2px'>{_e(str(data.get('title','')))}</div>"
        f"<div style='font-size:8.5px;color:{H(cfg['contact_color'])};margin-top:2px'>{_e(str(data.get('contact','')))}</div></div>")
    def sec(t):
        rule = f"border-bottom:{cfg['sec_rule_pdf']}px solid {H(cfg['sec_rule'])};" if cfg["sec_rule"] else ""
        P.append(f"<div style='font-size:10px;font-weight:800;color:{H(cfg['sec_color'])};margin:11px 0 5px;padding-bottom:2px;{rule}'>{_e(t)}</div>")
    def line(lbl, val):
        P.append(f"<div style='margin:2px 0'><b style='color:{TX}'>{_e(str(lbl))}</b>&nbsp; <span style='color:{MU}'>{_e(str(val))}</span></div>")
    def bul(t):
        P.append(f"<div style='margin:2px 0 2px 10px;color:{TX}'><span style='color:{H(cfg['bullet_color'])};font-weight:700'>{cfg['bullet']}</span>&nbsp; {_e(str(t))}</div>")
    sec("PROFESSIONAL SUMMARY"); P.append(f"<div style='color:{MU}'>{_e(str(data.get('summary','')))}</div>")
    if data.get("competencies"):
        sec("CORE COMPETENCIES")
        for c in data["competencies"]: line(c.get("label", ""), c.get("value", ""))
    sec(data.get("experience_heading", "WORK EXPERIENCE"))
    for job in data.get("experience", []):
        dates = f" <i style='color:{MU}'>&nbsp;{_e(str(job['dates']))}</i>" if job.get("dates") else ""
        P.append(f"<div style='margin-top:7px'><b style='color:{TX}'>{_e(str(job.get('title','')))}</b>"
                 f"<span style='color:#bbb'> &nbsp;|&nbsp; </span><b style='color:{CO}'>{_e(str(job.get('company','')))}</b>{dates}</div>")
        for b in job.get("bullets", []): bul(b)
    if data.get("skills"):
        sec("TECHNICAL SKILLS")
        for s in data["skills"]: line(s.get("label", ""), s.get("value", ""))
    if data.get("achievements"):
        sec("KEY ACHIEVEMENTS")
        for a in data["achievements"]: bul(a)
    sec("EDUCATION"); P.append(f"<div style='color:{MU}'>{_e(str(data.get('education','')))}</div>")
    if data.get("certifications"):
        sec("CERTIFICATIONS & LANGUAGES"); P.append(f"<div style='color:{MU}'>{_e(str(data['certifications']))}</div>")
    # single line on purpose: blank/indented lines would be parsed as markdown code
    return (f"<div style='background:#fff;color:{TX};font-family:{ff};font-size:10px;line-height:1.5;"
            f"padding:24px 28px;border-radius:6px;box-shadow:0 2px 14px rgba(0,0,0,.5);max-width:560px;margin:2px 0 10px'>"
            + "".join(P) + "</div>")

def pdf_page_previews(pdf_bytes, zoom=1.7, max_pages=2):
    """Render the first page(s) of a PDF to PNG bytes for the on-screen preview.
    Returns (pngs, total_pages). Fails soft: if rendering isn't available the
    app just skips the image preview instead of crashing."""
    try:
        try:
            import pymupdf as _mu
        except ImportError:
            import fitz as _mu
        doc = _mu.open(stream=pdf_bytes, filetype="pdf")
        total = doc.page_count
        pngs = [doc[i].get_pixmap(matrix=_mu.Matrix(zoom, zoom)).tobytes("png")
                for i in range(min(total, max_pages))]
        doc.close()
        return pngs, total
    except Exception as e:
        print(f"[preview] render failed: {e}")
        return [], 0

def render_resume_downloads(data, key_suffix, title, subtitle):
    """Format picker + PDF/DOCX download buttons. Regenerates files from the
    stored resume data whenever the chosen format changes (cached per data+format)."""
    st.markdown(f"""
<div class="dl-bar">
  <div class="dl-bar-title">{title}</div>
  <div class="dl-bar-sub">{subtitle}</div>
</div>""", unsafe_allow_html=True)
    tpl = st.selectbox("Resume format", list(RESUME_TEMPLATES.keys()),
        format_func=lambda k: RESUME_TEMPLATES[k]["label"], key=f"resume_tpl_{key_suffix}")
    sig = json.dumps(data, sort_keys=True, default=str) + "|" + tpl
    cache = st.session_state.get("_dl_cache") or {}
    if cache.get("sig") != sig:
        _pdf = make_pdf(data, tpl)
        _pngs, _pages = pdf_page_previews(_pdf)
        cache = {"sig": sig, "pdf": _pdf, "docx": make_docx(data, tpl), "pngs": _pngs, "pages": _pages}
        st.session_state["_dl_cache"] = cache
    st.markdown(
        f"<style>[data-testid='stImage'] img {{border:1px solid #2a2a2a;border-radius:6px;}}</style>"
        f"<div style='font-size:10px;font-weight:700;color:#888;letter-spacing:0.12em;margin:6px 0 8px'>"
        f"PREVIEW · {RESUME_TEMPLATES[tpl]['label'].split(' — ')[0].upper()} FORMAT</div>",
        unsafe_allow_html=True)
    if cache.get("pngs"):
        # exact page render of the file you will download
        for _png in cache["pngs"]:
            st.image(_png, width=560)
        if cache.get("pages", 0) > len(cache["pngs"]):
            st.caption(f"Showing the first {len(cache['pngs'])} of {cache['pages']} pages — the download has the full resume.")
    else:
        # always-available built-in preview (no extra libraries needed)
        st.markdown(resume_preview_html(data, tpl), unsafe_allow_html=True)
        st.caption("Preview of the selected format — your download uses the exact layout.")
    base = re.sub(r"[^A-Za-z0-9]+", "_", str(data.get("name", "") or "")).strip("_") or "ProfileIQ"
    d1, d2 = st.columns(2, gap="medium")
    with d1:
        st.download_button("⬇  Download PDF", data=cache["pdf"],
            file_name=f"{base}_Resume.pdf", mime="application/pdf",
            use_container_width=True, key=f"dl_pdf_{key_suffix}")
    with d2:
        st.download_button("⬇  Download Word (.docx)", data=cache["docx"],
            file_name=f"{base}_Resume.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True, key=f"dl_docx_{key_suffix}")


# ══════════════════════════════════════
# AUTH GATE — show login if not logged in
# ══════════════════════════════════════

def show_auth_page():
    st.markdown("""
<style>
.stApp { background: #0e0e0e !important; }
#MainMenu, footer { visibility: hidden !important; }
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="InputInstructions"] { display: none !important; }
/* Password visibility icon fix */
/* Constrain input width - works with st.columns */
[data-testid="stTextInput"] { max-width: 100% !important; }
[data-testid="stTextInput"] input { 
    max-width: 100% !important;
    font-size: 14px !important;
    padding: 10px 12px !important;
    background: #1e1e1e !important;
    border: 1px solid #333 !important;
    border-radius: 8px !important;
    color: #fff !important;
}
[data-testid="stTextInput"] input:focus { border-color: #F59E0B !important; box-shadow: none !important; }
[data-testid="stTextInput"] input::placeholder { color: #555 !important; }
/* Password field same styling */
[data-testid="stTextInputRootElement"] input,
[data-baseweb="input"] input { 
    background: #1e1e1e !important;
    border-color: #333 !important;
}
/* Hide password toggle button completely - removes "visibili" text */
[data-testid="stPasswordFieldToggle"] { display: none !important; }
/* Remove extra padding */
.block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }
/* Auth styles */
.auth-logo { display: flex; align-items: center; gap: 10px; justify-content: center; margin-bottom: 20px; }
.auth-logo-mark { background: #F59E0B; color: #1a1a1a; font-size: 14px; font-weight: 900; width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
.auth-logo-text { font-size: 28px; font-weight: 900; color: #fff; letter-spacing: -1px; }
.auth-logo-text span { color: #F59E0B; }
.auth-title { font-size: 22px; font-weight: 900; color: #fff; text-align: center; margin-bottom: 4px; }
.auth-sub { font-size: 13px; color: #666; text-align: center; margin-bottom: 20px; }
.free-badge { background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.3); border-radius: 8px; padding: 8px 14px; font-size: 12px; color: #F59E0B; text-align: center; margin-bottom: 16px; }
.auth-error { background: #2a1010; border: 1px solid #5a2020; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #f87171; margin-bottom: 12px; }
.auth-success { background: #0a2a1a; border: 1px solid #1a5a30; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #4ade80; margin-bottom: 12px; }
.auth-support-link { text-align: center; margin-top: 18px; }
.auth-support-link a { color: #666; font-size: 12px; text-decoration: none; border-bottom: 1px dotted #444; }
.auth-support-link a:hover { color: #F59E0B; border-color: #F59E0B; }
</style>
""", unsafe_allow_html=True)

    if "auth_show_support" not in st.session_state:
        st.session_state.auth_show_support = False

    # Use columns to constrain width - this is the ONLY reliable way in Streamlit
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown("""
<div class="auth-logo">
  <div class="auth-logo-mark">IQ</div>
  <div class="auth-logo-text">Profile<span>IQ</span></div>
</div>
""", unsafe_allow_html=True)

        view = st.session_state.auth_view

        if view == "login":
            st.markdown('<div class="auth-title">Welcome back</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-sub">Sign in to your ProfileIQ account</div>', unsafe_allow_html=True)
            email = st.text_input("Email", placeholder="you@email.com", key="login_email")
            password = st.text_input("Password", type="password", placeholder="Enter password", key="login_pass")
            if st.button("Sign in", type="primary", use_container_width=True):
                if email and password:
                    with st.spinner("Signing in..."):
                        res = sb_login(email, password)
                        if "access_token" in res:
                            st.session_state.access_token = res["access_token"]
                            st.session_state.user = res["user"]
                            profile = sb_get_profile(res["access_token"], res["user"]["id"])
                            profile = sb_reset_scans_if_needed(res["access_token"], res["user"]["id"], profile or {})
                            st.session_state.profile = profile
                    if "access_token" in res:
                        st.rerun()
                    else:
                        err = res.get("error_description", res.get("msg", "Invalid email or password"))
                        st.markdown(f'<div class="auth-error">⚠️ {err}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="auth-error">⚠️ Please enter email and password</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Forgot password?", use_container_width=True):
                    st.session_state.auth_view = "forgot"
                    st.rerun()
            with c2:
                if st.button("Create account", use_container_width=True):
                    st.session_state.auth_view = "register"
                    st.rerun()

        elif view == "register":
            st.markdown('<div class="auth-title">Create account</div>', unsafe_allow_html=True)
            st.markdown('<div class="free-badge">Free plan: 3 resume scans/month | No credit card needed</div>', unsafe_allow_html=True)
            name = st.text_input("Full name", placeholder="Your full name", key="reg_name")
            email = st.text_input("Email", placeholder="you@email.com", key="reg_email")
            mobile = st.text_input("Mobile number", placeholder="10-digit mobile, e.g. 98765 43210", key="reg_mobile")
            password = st.text_input("Password", type="password", placeholder="Min 6 characters", key="reg_pass")
            if st.button("Create account", type="primary", use_container_width=True):
                phone_norm = normalize_indian_mobile(mobile)
                if email and password and name and mobile:
                    if not is_valid_email(email):
                        st.markdown('<div class="auth-error">⚠️ Please enter a valid email address</div>', unsafe_allow_html=True)
                    elif not phone_norm:
                        st.markdown('<div class="auth-error">⚠️ Please enter a valid 10-digit Indian mobile number</div>', unsafe_allow_html=True)
                    elif len(password) < 6:
                        st.markdown('<div class="auth-error">⚠️ Password must be at least 6 characters</div>', unsafe_allow_html=True)
                    else:
                        with st.spinner("Creating account..."):
                            res = sb_register(email, password)
                        user_obj = res.get("user") or res
                        has_user = bool(user_obj.get("id")) or bool(res.get("id"))
                        if has_user:
                            login_res = sb_login(email, password)
                            if "access_token" in login_res:
                                st.session_state.access_token = login_res["access_token"]
                                st.session_state.user = login_res["user"]
                                uid = login_res["user"]["id"]
                                token = login_res["access_token"]
                                _pr = requests.patch(f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{uid}",
                                    headers={**sb_headers(token), "Prefer": "return=minimal"},
                                    json={"full_name": name, "phone": phone_norm})
                                if _pr.status_code not in (200, 204):
                                    # e.g. the `phone` column migration hasn't been run yet —
                                    # never lose the customer's name because of it.
                                    print(f"[signup] profile save with phone failed ({_pr.status_code}): {_pr.text[:200]}")
                                    requests.patch(f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{uid}",
                                        headers={**sb_headers(token), "Prefer": "return=minimal"},
                                        json={"full_name": name})
                                profile = sb_get_profile(token, uid)
                                st.session_state.profile = profile
                                st.rerun()
                            else:
                                st.markdown('<div class="auth-success">Account created! Please sign in.</div>', unsafe_allow_html=True)
                                st.session_state.auth_view = "login"
                                st.rerun()
                        else:
                            raw_err = res.get("msg", res.get("error_description", res.get("error", "")))
                            if "already" in str(raw_err).lower() or not raw_err:
                                err = "This email is already registered. Please sign in instead."
                            else:
                                err = raw_err
                            st.markdown(f'<div class="auth-error">⚠️ {err}</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="auth-error">⚠️ Please fill all fields</div>', unsafe_allow_html=True)
            if st.button("Back to sign in", use_container_width=True):
                st.session_state.auth_view = "login"
                st.rerun()

        elif view == "forgot":
            st.markdown('<div class="auth-title">Reset password</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-sub">Enter your registered email to receive a reset link</div>', unsafe_allow_html=True)
            email = st.text_input("Email", placeholder="you@email.com", key="forgot_email")
            if st.button("Send reset link", type="primary", use_container_width=True):
                if not email:
                    st.markdown('<div class="auth-error">⚠️ Please enter your email address</div>', unsafe_allow_html=True)
                elif '@' not in email or '.' not in email.split('@')[-1]:
                    st.markdown('<div class="auth-error">⚠️ Please enter a valid email address</div>', unsafe_allow_html=True)
                else:
                    with st.spinner("Sending reset link..."):
                        result = sb_forgot_password(email)
                    if result == 'invalid':
                        st.markdown('<div class="auth-error">⚠️ Please enter a valid email address</div>', unsafe_allow_html=True)
                    elif result == 'sent':
                        st.markdown('<div class="auth-success">✓ If this email is registered, you will receive a reset link shortly. Check your inbox.</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="auth-error">⚠️ Something went wrong. Please try again.</div>', unsafe_allow_html=True)
            if st.button("Back to sign in", use_container_width=True):
                st.session_state.auth_view = "login"
                st.rerun()

        st.markdown('<div class="auth-support-link">', unsafe_allow_html=True)
        if st.button("Having trouble? Contact support", key="auth_support_toggle", use_container_width=True):
            st.session_state.auth_show_support = not st.session_state.auth_show_support
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.auth_show_support:
            st.markdown("---")
            st.markdown("##### 💬 Contact Support")
            support_email = st.text_input("Your email", placeholder="you@email.com", key="auth_support_email")
            support_type = st.selectbox("Type", ["Login Issue", "Bug Report", "Feedback", "Other"], key="auth_support_type")
            support_message = st.text_area("Describe the issue", placeholder="Tell us what's going wrong...", height=100, key="auth_support_msg")
            sc1, sc2 = st.columns(2)
            with sc1:
                if st.button("Submit", type="primary", use_container_width=True, key="auth_support_submit"):
                    if not support_email or "@" not in support_email:
                        st.markdown('<div class="auth-error">⚠️ Please enter a valid email</div>', unsafe_allow_html=True)
                    elif not support_message.strip():
                        st.markdown('<div class="auth-error">⚠️ Please describe the issue</div>', unsafe_allow_html=True)
                    else:
                        with st.spinner("Submitting..."):
                            ok = sb_submit_support(support_email, support_type, support_message)
                        if ok:
                            st.markdown('<div class="auth-success">✓ Submitted! We\'ll get back to you soon.</div>', unsafe_allow_html=True)
                            st.session_state.auth_show_support = False
                        else:
                            st.markdown('<div class="auth-error">⚠️ Failed to submit. Please try again.</div>', unsafe_allow_html=True)
            with sc2:
                if st.button("Cancel", use_container_width=True, key="auth_support_cancel"):
                    st.session_state.auth_show_support = False
                    st.rerun()


def show_reset_password_page():
    st.markdown("""
<style>
.stApp { background: #0e0e0e !important; }
#MainMenu, footer, header { visibility: hidden !important; }
button[aria-label="Show password"], button[aria-label="Hide password"] { display: none !important; }
.auth-logo { display: flex; align-items: center; gap: 10px; justify-content: center; margin-bottom: 20px; }
.auth-logo-mark { background: #F59E0B; color: #1a1a1a; font-size: 14px; font-weight: 900; width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
.auth-logo-text { font-size: 28px; font-weight: 900; color: #fff; letter-spacing: -1px; }
.auth-logo-text span { color: #F59E0B; }
.auth-title { font-size: 22px; font-weight: 900; color: #fff; text-align: center; margin-bottom: 4px; }
.auth-sub { font-size: 13px; color: #666; text-align: center; margin-bottom: 20px; }
.auth-error { background: #2a1010; border: 1px solid #5a2020; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #f87171; margin-bottom: 12px; }
.auth-success { background: #0a2a1a; border: 1px solid #1a5a30; border-radius: 8px; padding: 10px 14px; font-size: 13px; color: #4ade80; margin-bottom: 12px; }
.block-container { padding-top: 2rem !important; }
</style>
""", unsafe_allow_html=True)

    token = st.query_params.get("reset_token", "")
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown('''
<div class="auth-logo">
  <div class="auth-logo-mark">IQ</div>
  <div class="auth-logo-text">Profile<span>IQ</span></div>
</div>
<div class="auth-title">Set new password</div>
<div class="auth-sub">Enter your new password below</div>
''', unsafe_allow_html=True)
        if not token:
            st.markdown('<div class="auth-error">⚠️ Invalid or expired link. Please request a new one.</div>', unsafe_allow_html=True)
            if st.button("Back to sign in", use_container_width=True):
                st.query_params.clear()
                st.rerun()
            return
        new_pass = st.text_input("New password", type="password", placeholder="Min 6 characters", key="new_pass")
        confirm_pass = st.text_input("Confirm password", type="password", placeholder="Repeat password", key="confirm_pass")
        if st.button("Update password", type="primary", use_container_width=True):
            if not new_pass or not confirm_pass:
                st.markdown('<div class="auth-error">⚠️ Please fill both fields</div>', unsafe_allow_html=True)
            elif len(new_pass) < 6:
                st.markdown('<div class="auth-error">⚠️ Password must be at least 6 characters</div>', unsafe_allow_html=True)
            elif new_pass != confirm_pass:
                st.markdown('<div class="auth-error">⚠️ Passwords do not match</div>', unsafe_allow_html=True)
            else:
                with st.spinner("Updating password..."):
                    r = requests.put(f"{SUPABASE_URL}/auth/v1/user",
                        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                        json={"password": new_pass})
                if r.status_code == 200:
                    st.markdown('<div class="auth-success">✓ Password updated! Please sign in.</div>', unsafe_allow_html=True)
                    import time; time.sleep(2)
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.markdown(f'<div class="auth-error">⚠️ Failed. Link may have expired. Request a new one.</div>', unsafe_allow_html=True)
        if st.button("Back to sign in", use_container_width=True, key="back_btn"):
            st.query_params.clear()
            st.rerun()

# ── TOP NAV (replaces the old app.html iframe wrapper) ──
st.markdown("""
<style>
.piq-nav {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 4px; margin: -1rem -1rem 12px -1rem; padding-left: 1rem; padding-right: 1rem;
    background: #1a1a1a; border-bottom: 1px solid #2a2a2a;
}
.piq-nav-logo, .piq-nav-logo:hover, .piq-nav-logo:visited {
    display: flex; align-items: center; gap: 8px;
    text-decoration: none !important; color: inherit !important;
}
.piq-logo-name { text-decoration: none !important; }
.piq-logo-mark { width: 30px; height: 30px; background: #F59E0B; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 900; color: #1a1a1a; }
.piq-logo-name { font-size: 16px; font-weight: 900; color: #fff; letter-spacing: -0.5px; }
.piq-logo-name span { color: #F59E0B; }
.piq-nav-badge { background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.3); color: #F59E0B; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 20px; }
</style>
<div class="piq-nav">
  <a href="https://profileiq.co.in/" class="piq-nav-logo" target="_blank" rel="noopener" style="text-decoration:none !important;color:inherit !important;display:flex;align-items:center;gap:8px;">
    <div class="piq-logo-mark">IQ</div>
    <div class="piq-logo-name">Profile<span>IQ</span></div>
  </a>
  <span class="piq-nav-badge">AI Powered</span>
</div>
""", unsafe_allow_html=True)

# Handle password reset from email
if st.query_params.get("reset_token", ""):
    show_reset_password_page()
    st.stop()

# Show auth page if not logged in
if not st.session_state.user:
    show_auth_page()
    st.stop()

# ── Refresh profile ──
profile = st.session_state.profile or {}
user_email = st.session_state.user.get("email", "") if st.session_state.user else ""
user_is_pro = is_pro(profile)
scans_left = free_scans_left(profile) if not user_is_pro else 999

# ── SUPPORT MODAL ──
def show_support_form():
    st.markdown("---")
    st.markdown("### 💬 Support")
    ticket_type = st.selectbox("Type", ["Feedback", "Bug Report", "Feature Request", "Other"], key="support_type")
    message = st.text_area("Message", placeholder="Tell us what's on your mind...", height=120, key="support_msg")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Submit", type="primary", use_container_width=True):
            if message.strip():
                with st.spinner("Submitting..."):
                    ok = sb_submit_support(user_email, ticket_type, message)
                if ok:
                    st.success("✓ Submitted! We'll get back to you at " + user_email)
                    st.session_state.show_support = False
                else:
                    st.error("Failed to submit. Please try again.")
            else:
                st.warning("Please enter a message")
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_support = False
            st.rerun()

# ── USER TOP BAR ── (above the hero panel, top of page)
plan_color = "#22c55e" if user_is_pro else "#F59E0B"
plan_label = "PRO" if user_is_pro else "FREE"
scans_info = "" if user_is_pro else f"{scans_left} free scans left"

st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;margin-bottom:12px;border-bottom:1px solid #2a2a2a">
  <div style="font-size:12px;color:#888">
    <b style="color:#fff">{user_email}</b>
    &nbsp;
    <span style="background:{plan_color}22;color:{plan_color};border:1px solid {plan_color}44;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px">{plan_label}</span>
    {f'&nbsp;<span style="color:#666;font-size:11px">{scans_info}</span>' if not user_is_pro else ''}
  </div>
</div>
""", unsafe_allow_html=True)

has_billing = user_is_pro or bool((profile or {}).get("razorpay_subscription_id"))
if has_billing:
    user_col1, user_col2, user_col3, user_col4 = st.columns([5.5, 1.6, 1.1, 1.1])
    with user_col2:
        if st.button("Manage" if user_is_pro else "Billing", use_container_width=True, key="btn_manage_sub"):
            st.session_state.show_manage_sub = not st.session_state.show_manage_sub
            st.session_state.confirm_cancel_sub = False
            st.rerun()
    with user_col3:
        if st.button("Support", use_container_width=True, key="btn_support"):
            st.session_state.show_support = not st.session_state.show_support
            st.rerun()
    with user_col4:
        if st.button("Sign out", use_container_width=True, key="btn_logout"):
            logout()
else:
    user_col1, user_col2, user_col3 = st.columns([7, 1, 1])
    with user_col2:
        if st.button("Support", use_container_width=True, key="btn_support"):
            st.session_state.show_support = not st.session_state.show_support
            st.rerun()
    with user_col3:
        if st.button("Sign out", use_container_width=True, key="btn_logout"):
            logout()

if st.session_state.show_manage_sub and has_billing:
    st.markdown("---")
    st.markdown("##### 📋 Manage Subscription" if user_is_pro else "##### 🧾 Billing")
    if user_is_pro:
        sub_status = profile.get("subscription_status", "active")
        expires_raw = profile.get("pro_expires_at")
        expires_display = expires_raw[:10] if expires_raw else "—"
        if sub_status == "cancel_at_cycle_end":
            st.markdown(f'<div class="auth-error">Your subscription is set to cancel. You\'ll keep Pro access until <b>{expires_display}</b>, then it won\'t renew.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="color:#888;font-size:13px;margin-bottom:12px">Next billing date: <b style="color:#fff">{expires_display}</b> · ₹199/month via UPI Autopay</div>', unsafe_allow_html=True)
            if not st.session_state.confirm_cancel_sub:
                if st.button("Cancel subscription", use_container_width=True, key="btn_cancel_sub_start"):
                    st.session_state.confirm_cancel_sub = True
                    st.rerun()
            else:
                st.markdown(f'<div class="auth-error">⚠️ You\'ll keep Pro access until <b>{expires_display}</b>, then it won\'t renew. This can\'t be undone from here.</div>', unsafe_allow_html=True)
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("Yes, cancel", type="primary", use_container_width=True, key="btn_cancel_sub_confirm"):
                        with st.spinner("Cancelling..."):
                            ok, err = cancel_subscription(profile.get("razorpay_subscription_id"), st.session_state.user["id"])
                        if ok:
                            fresh_profile = sb_get_profile(st.session_state.access_token, st.session_state.user["id"])
                            if fresh_profile:
                                st.session_state.profile = fresh_profile
                            st.session_state.confirm_cancel_sub = False
                            st.success("✓ Subscription cancelled — Pro access continues until your current period ends.")
                            st.rerun()
                        else:
                            st.markdown(f'<div class="auth-error">⚠️ {err}</div>', unsafe_allow_html=True)
                with cc2:
                    if st.button("Never mind", use_container_width=True, key="btn_cancel_sub_back"):
                        st.session_state.confirm_cancel_sub = False
                        st.rerun()
    else:
        st.markdown("<div style=\"color:#888;font-size:13px;margin-bottom:8px\">Your Pro plan isn't active right now. Your past invoices are below.</div>", unsafe_allow_html=True)
    render_invoices_panel(st.session_state.user["id"], user_email)
    st.markdown("---")

if st.session_state.show_support:
    show_support_form()

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── BUILD DYNAMIC HERO PANEL ──
before_score = st.session_state.analysis_result["score"] if st.session_state.analysis_result else None
after_score  = st.session_state.after_score
before_matched = st.session_state.analysis_result["matched"] if st.session_state.analysis_result else []
before_missing = st.session_state.analysis_result["missing"] if st.session_state.analysis_result else []
after_matched  = st.session_state.after_matched or []
after_missing  = st.session_state.after_missing or []

# Show keywords from latest analysis
show_matched = after_matched if after_matched else before_matched
show_missing = after_missing if after_missing else before_missing

if before_score is not None:
    before_cls = "before-high" if before_score >= 80 else "before-mid" if before_score >= 65 else "before-low"
    before_html = f'<div class="sc-box {before_cls}"><div class="sc-num">{before_score}</div><div class="sc-lbl">Before</div></div>'
else:
    before_html = '<div class="sc-box pending"><div class="sc-num">—</div><div class="sc-lbl">Before</div></div>'

if after_score is not None:
    after_html = f'<div class="sc-box after-done"><div class="sc-num">{after_score}</div><div class="sc-lbl">After AI</div></div>'
else:
    after_html = '<div class="sc-box pending"><div class="sc-num">—</div><div class="sc-lbl">After AI</div></div>'

kw_html = ""
for k in (show_matched[:4]):
    kw_html += f'<span class="kw hit">{k} ✓</span>'
for k in (show_missing[:4]):
    kw_html += f'<span class="kw miss">{k} ✗</span>'
if not kw_html:
    kw_html = '<span style="color:#bbb;font-size:11px;font-style:italic;">Analyze your resume to see keyword matches</span>'

st.markdown(f"""
<div class="hero">
  <div class="hero-left">
    <div>
      <div class="hero-logo">
        <div class="logo-mark">IQ</div>
        <div>
          <div class="logo-wordmark">Profile<span>IQ</span></div>
          <div class="logo-sub">AI Resume Intelligence</div>
        </div>
      </div>
      <div class="hero-headline">LAND THE<br><em>JOB.</em><br>NOT THE<br>REJECTION.</div>
      <div class="hero-body">ProfileIQ scores your resume against any job description, reveals every gap, and rewrites it to pass every ATS — in under 30 seconds.</div>
    </div>
    <div class="hero-stats">
      <div><div class="stat-num">30s</div><div class="stat-lbl">To analyze</div></div>
      <div><div class="stat-num">+28pt</div><div class="stat-lbl">Avg score lift</div></div>
      <div><div class="stat-num">100%</div><div class="stat-lbl">AI powered</div></div>
    </div>
  </div>
  <div class="hero-right">
    <div class="panel-title">Before vs after optimization</div>
    <div class="score-compare">
      {before_html}
      <div class="sc-arrow">→</div>
      {after_html}
    </div>
    <div class="kw-cloud">{kw_html}</div>
    {'' if before_score else '<div class="pending-msg">Analyze your resume to see live scores</div>'}
  </div>
</div>
""", unsafe_allow_html=True)

# ── MODE TOGGLE: Upload Resume vs Fresher (no resume yet) ──
resume_mode = st.radio("resume_mode_select",
    ["📄  Upload Resume", "🎓  I'm a Fresher — No Resume Yet"],
    horizontal=True, label_visibility="collapsed", key="resume_mode_radio")
st.session_state.is_fresher_mode = (resume_mode == "🎓  I'm a Fresher — No Resume Yet")
st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ── INPUTS ──
col1, col2 = st.columns(2, gap="medium")
with col1:
    if not st.session_state.is_fresher_mode:
        st.markdown("<p style='color:#fff;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px'>📄 Your Resume</p>", unsafe_allow_html=True)
        resume_file = st.file_uploader(
            "resume_upload",
            type=["pdf","doc","docx"],
            accept_multiple_files=False,
            label_visibility="collapsed"
        )

        # If the uploaded file no longer matches what was actually analyzed
        # (user swapped in a different resume), the old score/rewrite results
        # are for a resume that's no longer selected — clear them so the Hero
        # panel doesn't show stale after-AI data, and so Rewrite is blocked
        # until the new file is re-analyzed.
        _current_file_id = get_file_id(resume_file)
        if st.session_state.analysis_result is not None and _current_file_id != st.session_state.last_analyzed_file:
            st.session_state.analysis_result = None
            st.session_state.rewrite_data = None
            st.session_state.after_score = None
            st.session_state.after_matched = []
            st.session_state.after_missing = []
            st.session_state.last_analyzed_file = None
            st.session_state.last_analyzed_jd = None
            st.toast("⚠️ New resume detected — please re-analyze before rewriting.", icon="⚠️")
            st.rerun()
    else:
        resume_file = None
        st.markdown("<p style='color:#fff;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px'>🎓 Your Details</p>", unsafe_allow_html=True)

        # Load previously saved fresher data once per session
        if not st.session_state.fresher_loaded:
            saved = (profile.get("fresher_profile") or {}) if profile else {}
            if saved:
                st.session_state.fresher_full_name = saved.get("full_name", "")
                st.session_state.fresher_email = saved.get("email", "")
                st.session_state.fresher_phone = saved.get("phone", "")
                st.session_state.fresher_degree = saved.get("degree", "")
                st.session_state.fresher_institute = saved.get("institute", "")
                st.session_state.fresher_university = saved.get("university", "")
                st.session_state.fresher_year = saved.get("year_of_passing", "")
                st.session_state.fresher_skills = saved.get("key_skills", "")
                if saved.get("projects"):
                    st.session_state.fresher_projects = saved["projects"]
                if saved.get("certifications"):
                    st.session_state.fresher_certifications = saved["certifications"]
            st.session_state.fresher_loaded = True

        fc1, fc2 = st.columns(2)
        with fc1:
            st.text_input("Full Name", key="fresher_full_name", placeholder="Jane Doe")
            st.text_input("Degree", key="fresher_degree", placeholder="B.Tech Computer Science")
            st.text_input("Institute", key="fresher_institute", placeholder="XYZ Institute of Technology")
            st.text_input("Year of Passing", key="fresher_year", placeholder="2026")
        with fc2:
            st.text_input("Email", key="fresher_email", placeholder="jane@email.com")
            st.text_input("Phone", key="fresher_phone", placeholder="+91 98765 43210")
            st.text_input("University", key="fresher_university", placeholder="XYZ University")
            st.text_input("Key Skills (comma separated)", key="fresher_skills", placeholder="Python, SQL, React, Git")

        st.markdown("<div style='font-size:11px;color:#888;font-weight:700;margin:10px 0 4px'>ACADEMIC PROJECTS</div>", unsafe_allow_html=True)
        for i, proj in enumerate(st.session_state.fresher_projects):
            pc1, pc2, pc3 = st.columns([2, 3, 0.5])
            with pc1:
                st.session_state.fresher_projects[i]["name"] = st.text_input(
                    "Project name", value=proj.get("name", ""), key=f"fresher_proj_name_{i}",
                    placeholder="Project name", label_visibility="collapsed")
            with pc2:
                st.session_state.fresher_projects[i]["description"] = st.text_input(
                    "Description", value=proj.get("description", ""), key=f"fresher_proj_desc_{i}",
                    placeholder="Brief description — what it does, tech used", label_visibility="collapsed")
            with pc3:
                if len(st.session_state.fresher_projects) > 1:
                    if st.button("✕", key=f"fresher_proj_remove_{i}"):
                        st.session_state.fresher_projects.pop(i)
                        st.rerun()
        if st.button("+ Add another project", key="fresher_add_project"):
            st.session_state.fresher_projects.append({"name": "", "description": ""})
            st.rerun()

        st.markdown("<div style='font-size:11px;color:#888;font-weight:700;margin:14px 0 4px'>CERTIFICATIONS</div>", unsafe_allow_html=True)
        for i, cert in enumerate(st.session_state.fresher_certifications):
            cc1, cc2 = st.columns([5, 0.5])
            with cc1:
                st.session_state.fresher_certifications[i]["name"] = st.text_input(
                    "Certification", value=cert.get("name", ""), key=f"fresher_cert_name_{i}",
                    placeholder="e.g. AWS Cloud Practitioner", label_visibility="collapsed")
            with cc2:
                if len(st.session_state.fresher_certifications) > 1:
                    if st.button("✕", key=f"fresher_cert_remove_{i}"):
                        st.session_state.fresher_certifications.pop(i)
                        st.rerun()
        if st.button("+ Add another certification", key="fresher_add_cert"):
            st.session_state.fresher_certifications.append({"name": ""})
            st.rerun()

with col2:
    st.markdown("<p style='color:#fff;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px'>💼 Job Description</p>", unsafe_allow_html=True)
    jd_text = st.text_area("jd_input", height=145,
        placeholder="Paste the full job description here — the more detail, the better the match...",
        label_visibility="collapsed")

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

if not st.session_state.is_fresher_mode:
    # ── TABS ──
    has_score = st.session_state.analysis_result is not None

    # ── TABS ── rewrite disabled until scored
    tab_choice = st.radio("tab_select",
        ["📊  Score my resume", "✨  Rewrite with AI"],
        horizontal=True, label_visibility="collapsed")
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # Show lock message if rewrite selected but no score yet
    if tab_choice == "✨  Rewrite with AI" and not has_score:
        st.markdown("""
    <div style="background:#2a1f0a;border:1px solid #5a4010;border-radius:10px;padding:16px 20px;margin-bottom:16px;display:flex;align-items:center;gap:12px">
      <span style="font-size:24px">🔒</span>
      <div>
        <div style="color:#F59E0B;font-weight:700;font-size:13px;margin-bottom:3px">Score your resume first</div>
        <div style="color:#888;font-size:12px">Switch to the <b style="color:#fff">Score my resume</b> tab, analyze your resume against the JD, then come back to rewrite.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── JS: injected in main CSS block ──
    st.markdown("""
    <script>
    function fixUploadButton() {
        var btn = document.querySelector('[data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"]');
        if (!btn || btn.dataset.fixed) return;
        // Remove icon from DOM entirely — no layout side effects
        btn.querySelectorAll('[data-testid="stIconMaterial"]').forEach(icon => icon.remove());
        // Set clean text only
        btn.innerHTML = 'UPLOAD';
        btn.style.cssText = 'width:100%!important;display:block!important;text-align:center!important;background:#F59E0B!important;color:#1a1a1a!important;border:none!important;border-radius:8px!important;padding:12px 24px!important;font-weight:800!important;font-size:13px!important;text-transform:uppercase!important;letter-spacing:0.06em!important;font-family:Inter,sans-serif!important;cursor:pointer!important;box-sizing:border-box!important;line-height:normal!important;';
        btn.dataset.fixed = '1';
    }

    function fixExpander() {
        // Hide the material arrow icon text content inside expander summary
        // It renders as stIconMaterial with text "keyboard_arrow_right/down"
        document.querySelectorAll('[data-testid="stExpander"] summary [data-testid="stIconMaterial"]').forEach(icon => {
            icon.style.fontSize = '0';
            icon.style.overflow = 'hidden';
            icon.style.width = '16px';
            icon.style.height = '16px';
            icon.style.display = 'inline-block';
        });
        // Ensure label text is visible and styled
        document.querySelectorAll('[data-testid="stExpander"] summary p').forEach(p => {
            p.style.color = '#aaa';
            p.style.fontSize = '13px';
            p.style.fontWeight = '600';
        });
    }

    setTimeout(fixUploadButton, 200);
    setTimeout(fixUploadButton, 600);
    setInterval(fixUploadButton, 2000);
    setTimeout(fixExpander, 200);
    setTimeout(fixExpander, 600);
    setTimeout(fixExpander, 1200);
    setInterval(fixExpander, 2500);
    </script>
    """, unsafe_allow_html=True)

    def validate():
        ok = True
        if not resume_file:
            st.markdown('<div class="warn-badge">⚠️ Upload your resume to continue.</div>', unsafe_allow_html=True)
            ok = False
        elif not jd_text.strip():
            st.markdown('<div class="warn-badge">⚠️ Paste a job description to continue.</div>', unsafe_allow_html=True)
            ok = False
        return ok

    # ════════════════════════
    # SCORE TAB
    # ════════════════════════
    if tab_choice == "📊  Score my resume":
        show_ai_error("analyze")
        c1, c2 = st.columns([5,1], gap="small")
        with c1:
            if not user_is_pro and scans_left <= 0:
                st.markdown("""
    <div style="background:#2a1010;border:1px solid #5a2020;border-radius:10px;padding:16px 20px;margin-bottom:12px;text-align:center">
      <div style="color:#f87171;font-weight:700;font-size:14px;margin-bottom:6px">You have used all 3 free scans this month</div>
      <div style="color:#888;font-size:12px;margin-bottom:12px">Upgrade to Pro for unlimited scans, AI rewrite and downloads.</div>
    </div>
    """, unsafe_allow_html=True)
                render_upgrade_cta("scanlimit")
                analyze_clicked = False
            else:
                analyze_clicked = st.button("Analyze now", type="primary",
                    use_container_width=True, key="btn_analyze",
                    disabled=st.session_state.processing)
        with c2:
            if st.button("Clear", type="secondary", use_container_width=True, key="btn_clear"):
                st.session_state.analysis_result = None
                st.session_state.last_analyzed_file = None
                st.session_state.last_analyzed_jd = None
                st.rerun()

        if analyze_clicked and not st.session_state.processing:
            if validate():
                if (get_file_id(resume_file) == st.session_state.last_analyzed_file and
                    jd_text.strip() == st.session_state.last_analyzed_jd):
                    st.markdown('<div class="info-badge">ℹ️ Already analyzed this combination. Change the resume or JD to analyze again.</div>', unsafe_allow_html=True)
                else:
                    st.session_state.processing = True
                    st.session_state.ai_error = None
                    with st.spinner("Analyzing your resume against the job description..."):
                        try:
                            # Check scan limit for free users
                            if not user_is_pro and scans_left <= 0:
                                st.markdown('<div class="warn-badge">You have used all 3 free scans this month. Upgrade to Pro for unlimited scans.</div>', unsafe_allow_html=True)
                                st.stop()
                            rt = extract_text(resume_file)
                            if not (rt or "").strip():
                                raise ValueError("EMPTY_RESUME")
                            scored = score_resume(rt, jd_text)
                            sugs   = get_suggestions(rt, jd_text, scored["score"], scored["missing"])
                            scored["suggestions"] = sugs
                            st.session_state.analysis_result = scored
                            st.session_state.last_analyzed_file = get_file_id(resume_file)
                            st.session_state.last_analyzed_jd = jd_text.strip()
                            # Increment scan count for free users
                            if not user_is_pro:
                                current_used = st.session_state.profile.get("scans_used", 0) if st.session_state.profile else 0
                                sb_increment_scan(st.session_state.access_token, st.session_state.user["id"], current_used)
                                # Update local profile so counter reflects immediately
                                if st.session_state.profile:
                                    st.session_state.profile["scans_used"] = current_used + 1
                        except Exception as e:
                            st.session_state.ai_error = {"ctx": "analyze", **describe_ai_error(e)}
                        finally:
                            st.session_state.processing = False
                    st.rerun()

        if st.session_state.analysis_result:
            p = st.session_state.analysis_result
            score = p["score"]
            if score >= 80:
                verdict = "🎉 Great fit for this position!"
                score_color = "#22c55e"
                verdict_color = "#22c55e"
            elif score >= 65:
                verdict = "Good — room to improve"
                score_color = "#F59E0B"
                verdict_color = "#F59E0B"
            else:
                verdict = "Needs work — use AI rewrite"
                score_color = "#ef4444"
                verdict_color = "#ef4444"
            sugs_label = "How to stand out further" if score >= 80 else "How to improve your score" if score >= 65 else "Critical gaps to fix"
            mh  = "".join(f'<span class="kw hit">{k} ✓</span>' for k in p["matched"] if k)
            msh = "".join(f'<span class="kw miss">{k} ✗</span>' for k in p["missing"] if k)
            sh  = "".join(f'<div class="sug-item"><div class="sug-n">0{i+1}</div><div class="sug-t">{s}</div></div>'
                          for i,s in enumerate(p.get("suggestions",[])[:5]) if s)
            st.markdown(f"""
    <div class="results-wrap">
      <div class="score-panel">
        <div class="sp-label">ATS score</div>
        <div class="sp-num" style="color:{score_color}">{score}</div>
        <div class="sp-denom">out of 100</div>
        <div class="sp-bar"><div class="sp-bar-fill" style="width:{min(score,100)}%;background:{score_color}"></div></div>
        <div class="sp-verdict" style="color:{verdict_color};font-weight:600">{verdict}</div>
      </div>
      <div class="detail-panel">
        <div class="dp-section">Matched keywords</div>
        <div class="kw-group">{mh or '<span style="color:#555;font-size:11px;">None found</span>'}</div>
        <div class="dp-section">Missing keywords</div>
        <div class="kw-group">{msh or '<span style="color:#4ade80;font-size:11px;">All matched!</span>'}</div>
        <div class="dp-section">{sugs_label}</div>
        <div class="suggestions">{sh}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ════════════════════════
    # REWRITE TAB
    # ════════════════════════
    elif tab_choice == "✨  Rewrite with AI" and has_score:
        # Show upgrade banner for free users
        if not user_is_pro:
            st.markdown("""
    <div style="background:#2a1f0a;border:1px solid #5a4010;border-radius:10px;padding:16px 20px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="color:#F59E0B;font-weight:700;font-size:13px;margin-bottom:3px">Pro feature — AI Resume Rewrite</div>
        <div style="color:#888;font-size:12px">Upgrade to Pro (Rs.199/month) to unlock unlimited rewrites, PDF/DOCX downloads and more.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
            render_upgrade_cta("rewritetab")
            st.stop()

        show_ai_error("rewrite")
        c3, c4 = st.columns([5,1], gap="small")
        with c3:
            rewrite_clicked = st.button("Rewrite with AI ->", type="primary",
                use_container_width=True, key="btn_rewrite",
                disabled=st.session_state.processing)
        with c4:
            if st.button("Clear", type="secondary", use_container_width=True, key="btn_clear2"):
                st.session_state.rewrite_data = None
                st.session_state.docx_bytes = None
                st.session_state.pdf_bytes = None
                st.session_state.after_score = None
                st.session_state.after_matched = []
                st.session_state.after_missing = []
                st.session_state.last_rewritten_file = None
                st.session_state.last_rewritten_jd = None
                st.rerun()

        if rewrite_clicked and not st.session_state.processing:
            if validate():
                if (get_file_id(resume_file) == st.session_state.last_rewritten_file and
                    jd_text.strip() == st.session_state.last_rewritten_jd):
                    st.markdown('<div class="info-badge">ℹ️ Already rewritten. Change resume or JD to rewrite again.</div>', unsafe_allow_html=True)
                else:
                    st.session_state.processing = True
                    st.session_state.ai_error = None
                    with st.spinner("✨ Rewriting your resume and scoring the result..."):
                        try:
                            rt = extract_text(resume_file)
                            if not (rt or "").strip():
                                raise ValueError("EMPTY_RESUME")
                            # Step 1: Rewrite aggressively for ATS
                            data = do_rewrite(rt, jd_text)
                            # Step 2: Build complete text from ALL rewritten fields for scoring
                            rewritten_parts = [
                                data.get("name",""),
                                data.get("title",""),
                                data.get("contact",""),
                                data.get("summary",""),
                            ]
                            for c in data.get("competencies",[]):
                                rewritten_parts.append(f"{c.get('label','')} {c.get('value','')}")
                            for j in data.get("experience",[]):
                                rewritten_parts.append(f"{j.get('title','')} {j.get('company','')} {j.get('dates','')}")
                                for b in j.get("bullets",[]):
                                    rewritten_parts.append(b)
                            for sk in data.get("skills",[]):
                                rewritten_parts.append(f"{sk.get('label','')} {sk.get('value','')}")
                            for a in data.get("achievements",[]):
                                rewritten_parts.append(a)
                            rewritten_parts.append(data.get("education",""))
                            rewritten_parts.append(data.get("certifications",""))
                            rewritten_text = "\n".join(p for p in rewritten_parts if p)
                            after_scored = score_resume(rewritten_text, jd_text)
                            # Store everything
                            st.session_state.rewrite_data = data
                            st.session_state.docx_bytes = make_docx(data)
                            st.session_state.pdf_bytes  = make_pdf(data)
                            st.session_state.after_score   = after_scored["score"]
                            st.session_state.after_matched = after_scored["matched"]
                            st.session_state.after_missing = after_scored["missing"]
                            st.session_state.last_rewritten_file = get_file_id(resume_file)
                            st.session_state.last_rewritten_jd = jd_text.strip()
                        except Exception as e:
                            st.session_state.ai_error = {"ctx": "rewrite", **describe_ai_error(e)}
                        finally:
                            st.session_state.processing = False
                    st.rerun()

        if st.session_state.rewrite_data and st.session_state.pdf_bytes:
            data = st.session_state.rewrite_data
            render_resume_downloads(data, "rewrite",
                "Your optimized resume is ready ✓",
                "ATS score updated in the dashboard above · Choose a format and download below")

            # ── FULL PREVIEW ──
            with st.expander("Preview rewritten resume"):
                d = st.session_state.rewrite_data

                # Header
                st.markdown(f"<div style='font-size:22px;font-weight:900;color:#fff;margin-bottom:4px'>{d.get('name','')}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:13px;color:#F59E0B;font-weight:600;margin-bottom:6px'>{d.get('title','')}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:11px;color:#666;margin-bottom:16px'>{d.get('contact','')}</div>", unsafe_allow_html=True)
                st.divider()

                # Summary
                st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Professional Summary</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:12px;color:#aaa;line-height:1.7'>{d.get('summary','')}</div>", unsafe_allow_html=True)

                # Competencies
                if d.get("competencies"):
                    st.divider()
                    st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Core Competencies</div>", unsafe_allow_html=True)
                    for c in d["competencies"]:
                        st.markdown(f"<div style='font-size:12px;color:#aaa;margin-bottom:4px'><span style='color:#fff;font-weight:700'>{c['label']}</span> &nbsp; {c['value']}</div>", unsafe_allow_html=True)

                # Experience
                st.divider()
                st.markdown(f"<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:10px'>{d.get('experience_heading', 'Work Experience').title()}</div>", unsafe_allow_html=True)
                for job in d.get("experience", []):
                    st.markdown(f"<div style='font-size:13px;font-weight:700;color:#fff;margin-bottom:2px;margin-top:12px'>{job.get('title','')} &nbsp;|&nbsp; <span style='color:#F59E0B'>{job.get('company','')}</span></div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:11px;color:#666;margin-bottom:6px'>{job.get('dates','')}</div>", unsafe_allow_html=True)
                    for b in job.get("bullets", []):
                        st.markdown(f"<div style='font-size:12px;color:#aaa;line-height:1.6;padding-left:14px;margin-bottom:3px'>▸ &nbsp;{b}</div>", unsafe_allow_html=True)

                # Skills
                if d.get("skills"):
                    st.divider()
                    st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Technical Skills</div>", unsafe_allow_html=True)
                    for s in d["skills"]:
                        st.markdown(f"<div style='font-size:12px;color:#aaa;margin-bottom:4px'><span style='color:#fff;font-weight:700'>{s['label']}</span> &nbsp; {s['value']}</div>", unsafe_allow_html=True)

                # Achievements
                if d.get("achievements"):
                    st.divider()
                    st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Key Achievements</div>", unsafe_allow_html=True)
                    for a in d["achievements"]:
                        st.markdown(f"<div style='font-size:12px;color:#aaa;line-height:1.6;padding-left:14px;margin-bottom:3px'>▸ &nbsp;{a}</div>", unsafe_allow_html=True)

                # Education
                st.divider()
                st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Education</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:12px;color:#aaa'>{d.get('education','')}</div>", unsafe_allow_html=True)

                # Certifications
                if d.get("certifications"):
                    st.divider()
                    st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Certifications & Languages</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size:12px;color:#aaa'>{d.get('certifications','')}</div>", unsafe_allow_html=True)

else:
    # ════════════════════════
    # FRESHER: BUILD RESUME
    # ════════════════════════
    if not user_is_pro:
        st.markdown("""
<div style="background:#2a1f0a;border:1px solid #5a4010;border-radius:10px;padding:16px 20px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between">
  <div>
    <div style="color:#F59E0B;font-weight:700;font-size:13px;margin-bottom:3px">Pro feature — Build Resume for Freshers</div>
    <div style="color:#888;font-size:12px">Upgrade to Pro (Rs.199/month) to build a fully AI-optimized resume from your education, projects and skills.</div>
  </div>
</div>
""", unsafe_allow_html=True)
        render_upgrade_cta("freshertab")
        st.stop()

    show_ai_error("fresher")
    build_clicked = st.button("Build My Resume ->", type="primary",
        use_container_width=True, key="btn_build_fresher",
        disabled=st.session_state.processing)

    if build_clicked and not st.session_state.processing:
        fresher_data = {
            "full_name": st.session_state.get("fresher_full_name", "").strip(),
            "email": st.session_state.get("fresher_email", "").strip(),
            "phone": st.session_state.get("fresher_phone", "").strip(),
            "degree": st.session_state.get("fresher_degree", "").strip(),
            "institute": st.session_state.get("fresher_institute", "").strip(),
            "university": st.session_state.get("fresher_university", "").strip(),
            "year_of_passing": st.session_state.get("fresher_year", "").strip(),
            "key_skills": st.session_state.get("fresher_skills", "").strip(),
            "projects": [p for p in st.session_state.fresher_projects if p.get("name", "").strip()],
            "certifications": [c for c in st.session_state.fresher_certifications if c.get("name", "").strip()],
        }
        missing_fields = []
        if not fresher_data["full_name"]: missing_fields.append("Full Name")
        if not fresher_data["email"]: missing_fields.append("Email")
        if not fresher_data["degree"]: missing_fields.append("Degree")
        if not fresher_data["institute"]: missing_fields.append("Institute")
        if not fresher_data["key_skills"]: missing_fields.append("Key Skills")
        if not jd_text.strip(): missing_fields.append("Job Description")

        if missing_fields:
            st.markdown(f'<div class="auth-error">⚠️ Please fill in: {", ".join(missing_fields)}</div>', unsafe_allow_html=True)
        else:
            st.session_state.processing = True
            st.session_state.ai_error = None
            with st.spinner("✨ Building your resume and scoring it against the job description..."):
                try:
                    data = build_fresher_resume(fresher_data, jd_text)
                    rewritten_parts = [
                        data.get("name",""), data.get("title",""), data.get("contact",""), data.get("summary",""),
                    ]
                    for c in data.get("competencies",[]):
                        rewritten_parts.append(f"{c.get('label','')} {c.get('value','')}")
                    for j in data.get("experience",[]):
                        rewritten_parts.append(f"{j.get('title','')} {j.get('company','')} {j.get('dates','')}")
                        for b in j.get("bullets",[]):
                            rewritten_parts.append(b)
                    for sk in data.get("skills",[]):
                        rewritten_parts.append(f"{sk.get('label','')} {sk.get('value','')}")
                    rewritten_parts.append(data.get("education",""))
                    rewritten_parts.append(data.get("certifications",""))
                    rewritten_text = "\n".join(p for p in rewritten_parts if p)
                    after_scored = score_resume(rewritten_text, jd_text)

                    st.session_state.rewrite_data = data
                    st.session_state.docx_bytes = make_docx(data)
                    st.session_state.pdf_bytes  = make_pdf(data)
                    st.session_state.after_score   = after_scored["score"]
                    st.session_state.after_matched = after_scored["matched"]
                    st.session_state.after_missing = after_scored["missing"]

                    # Save fresher data for next time
                    sb_save_fresher_profile(st.session_state.access_token, st.session_state.user["id"], fresher_data)
                except Exception as e:
                    st.session_state.ai_error = {"ctx": "fresher", **describe_ai_error(e)}
                finally:
                    st.session_state.processing = False
            st.rerun()

    if st.session_state.rewrite_data and st.session_state.pdf_bytes:
        data = st.session_state.rewrite_data
        render_resume_downloads(data, "fresher",
            "Your resume is ready ✓",
            "ATS score shown in the dashboard above · Choose a format and download below")

        with st.expander("Preview your resume"):
            d = st.session_state.rewrite_data
            st.markdown(f"<div style='font-size:22px;font-weight:900;color:#fff;margin-bottom:4px'>{d.get('name','')}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:13px;color:#F59E0B;font-weight:600;margin-bottom:6px'>{d.get('title','')}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:11px;color:#666;margin-bottom:16px'>{d.get('contact','')}</div>", unsafe_allow_html=True)
            st.divider()

            st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Professional Summary</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:12px;color:#aaa;line-height:1.7'>{d.get('summary','')}</div>", unsafe_allow_html=True)

            if d.get("competencies"):
                st.divider()
                st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Core Competencies</div>", unsafe_allow_html=True)
                for c in d["competencies"]:
                    st.markdown(f"<div style='font-size:12px;color:#aaa;margin-bottom:4px'><span style='color:#fff;font-weight:700'>{c['label']}</span> &nbsp; {c['value']}</div>", unsafe_allow_html=True)

            st.divider()
            st.markdown(f"<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:10px'>{d.get('experience_heading', 'Projects').title()}</div>", unsafe_allow_html=True)
            for job in d.get("experience", []):
                st.markdown(f"<div style='font-size:13px;font-weight:700;color:#fff;margin-bottom:2px;margin-top:12px'>{job.get('title','')} &nbsp;|&nbsp; <span style='color:#F59E0B'>{job.get('company','')}</span></div>", unsafe_allow_html=True)
                if job.get('dates'):
                    st.markdown(f"<div style='font-size:11px;color:#666;margin-bottom:6px'>{job.get('dates','')}</div>", unsafe_allow_html=True)
                for b in job.get("bullets", []):
                    st.markdown(f"<div style='font-size:12px;color:#aaa;line-height:1.6;padding-left:14px;margin-bottom:3px'>▸ &nbsp;{b}</div>", unsafe_allow_html=True)

            if d.get("skills"):
                st.divider()
                st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Technical Skills</div>", unsafe_allow_html=True)
                for s in d["skills"]:
                    st.markdown(f"<div style='font-size:12px;color:#aaa;margin-bottom:4px'><span style='color:#fff;font-weight:700'>{s['label']}</span> &nbsp; {s['value']}</div>", unsafe_allow_html=True)

            st.divider()
            st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Education</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:12px;color:#aaa'>{d.get('education','')}</div>", unsafe_allow_html=True)

            if d.get("certifications"):
                st.divider()
                st.markdown("<div style='font-size:9px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px'>Certifications</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:12px;color:#aaa'>{d.get('certifications','')}</div>", unsafe_allow_html=True)
