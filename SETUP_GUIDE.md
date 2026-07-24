# ProfileIQ — Razorpay Subscription Fix: Setup Guide

## What was broken
Both `index.html` and `app.py` linked to a **static Razorpay Payment Link**
(`rzp.io/rzp/FmC2uaMo`). Nothing in the code ever updated a user's `plan` or
`pro_expires_at` in Supabase after payment — it relied on users typing their
email correctly into a note, with someone presumably updating the database
by hand. There was no webhook, no automation.

## What's fixed
- Each "Upgrade to Pro" click now creates a **real Razorpay Subscription**
  tied to the logged-in user's ID (via `notes.user_id`), and opens Razorpay
  Checkout embedded in the app.
- A new **Supabase Edge Function** (`razorpay-webhook`) receives Razorpay's
  webhook events, verifies the signature, and automatically sets
  `plan='pro'` + `pro_expires_at` on the correct profile — no manual work,
  no email-matching required.
- Renewals (`subscription.charged`) extend `pro_expires_at` automatically
  every month. Failed renewals or cancellations don't yank access
  immediately — the user keeps Pro until the period they already paid for
  actually ends.

---

## Step 1 — Run the database migration
In Supabase Dashboard → SQL Editor, run `01_supabase_migration.sql`
(included). It adds `razorpay_customer_id`, `razorpay_subscription_id`, and
`subscription_status` columns to `profiles`.

## Step 2 — Create a Razorpay Plan
Subscriptions need a Plan ID. Run once (replace with your live/test keys):

```bash
curl -u <RAZORPAY_KEY_ID>:<RAZORPAY_KEY_SECRET> \
  -X POST https://api.razorpay.com/v1/plans \
  -H "Content-Type: application/json" \
  -d '{
    "period": "monthly",
    "interval": 1,
    "item": {
      "name": "ProfileIQ Pro",
      "amount": 19900,
      "currency": "INR",
      "description": "Unlimited scans, AI rewrite, PDF/DOCX downloads"
    }
  }'
```

Save the returned `id` (looks like `plan_xxxxxxxxxxxxx`) — this is your
`RAZORPAY_PLAN_ID`.

> Note: Subscriptions require your Razorpay account to have Subscriptions
> enabled (usually needs KYC/activation completed — check Dashboard →
> Subscriptions if the API call above fails with a permissions error).

## Step 3 — Deploy the webhook (Supabase Edge Function)
Requires the [Supabase CLI](https://supabase.com/docs/guides/cli).

```bash
supabase login
supabase link --project-ref <your-project-ref>

# Set the secrets the function needs:
supabase secrets set RAZORPAY_WEBHOOK_SECRET=<choose-a-strong-random-string>
supabase secrets set SB_URL=https://<your-project-ref>.supabase.co
supabase secrets set SB_SERVICE_ROLE_KEY=<your-service-role-key>

# Deploy (--no-verify-jwt because Razorpay calls this, not a logged-in user)
supabase functions deploy razorpay-webhook --no-verify-jwt
```

Your webhook URL will be:
`https://<your-project-ref>.functions.supabase.co/razorpay-webhook`

## Step 4 — Register the webhook in Razorpay
Dashboard → Settings → Webhooks → Add New Webhook:
- **URL:** the function URL from Step 3
- **Secret:** the exact same string you set as `RAZORPAY_WEBHOOK_SECRET`
- **Active events:** `subscription.activated`, `subscription.charged`,
  `subscription.pending`, `subscription.halted`, `subscription.cancelled`,
  `subscription.completed`

## Step 5 — Add secrets to your app
In Railway (or wherever `app.py` reads `st.secrets` / env vars from),
add:
```
RAZORPAY_KEY_ID=<your key id>
RAZORPAY_KEY_SECRET=<your key secret>
RAZORPAY_PLAN_ID=<plan_xxxxxxxxxxxxx from Step 2>
```

## Step 6 — Deploy the updated files
Replace `app.py`, `requirements.txt`, and `index.html` with the versions in
this folder, then redeploy on Railway as usual (`git push`, or however your
pipeline works).

## Step 7 — Test end-to-end (use Razorpay Test Mode keys first!)
1. Log into the app, click **Upgrade to Pro**.
2. Complete checkout with a [Razorpay test card](https://razorpay.com/docs/payments/payments/test-card-upi-details/).
3. Click **Refresh my Pro status** — the badge should flip to PRO.
4. In Razorpay Dashboard → Test Mode → Subscriptions, use **Charge this
   now** to simulate a renewal and confirm `pro_expires_at` extends via
   the webhook logs (Supabase Dashboard → Edge Functions → Logs).
5. Switch to live keys/plan only after this all checks out.

---

## Files in this delivery
| File | Purpose |
|---|---|
| `01_supabase_migration.sql` | Adds subscription-tracking columns |
| `supabase/functions/razorpay-webhook/index.ts` | Webhook receiver, verifies signature, updates profile |
| `app.py` | Updated: creates subscriptions, embeds Razorpay Checkout, refresh-status button |
| `requirements.txt` | Added `razorpay` SDK |
| `index.html` | "Get Pro" now routes into the logged-in app instead of an anonymous payment link |
