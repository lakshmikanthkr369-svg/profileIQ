"""All configuration comes from environment variables (set them in Railway). No secrets in code."""
import os

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://adybtayirxocljwkydyg.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")      # public key: used only to verify a login token
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_KEY", "")        # SECRET service-role key: server only

# Comma-separated list of browser origins allowed to call this API
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS", "https://app.profileiq.co.in,http://localhost:3000").split(",") if o.strip()]

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
FREE_SCANS_PER_MONTH = 3
# AI calls allowed per user in a rolling window (protects your Anthropic bill)
AI_CALLS_PER_WINDOW = int(os.getenv("AI_CALLS_PER_WINDOW", "10"))
AI_WINDOW_SECONDS = int(os.getenv("AI_WINDOW_SECONDS", "300"))

# Razorpay (subscriptions). Key ID is public (the checkout needs it); the secret stays on the server.
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_PLAN_ID = os.getenv("RAZORPAY_PLAN_ID", "")

# Email (Resend) for invoice copies and support notifications
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
INVOICE_FROM = os.getenv("INVOICE_FROM", "ProfileIQ <support@profileiq.co.in>")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@profileiq.co.in")
OWNER_NOTIFY_EMAIL = os.getenv("OWNER_NOTIFY_EMAIL", "lakshmikanthkr3@gmail.com")
