# ProfileIQ cutover runbook (Streamlit -> Next.js + FastAPI)

## Before cutover (do in this order)
1. **Rotate secrets** (they were in git history): Supabase JWT secret -> new anon + service keys; Razorpay test key. Update Railway `profileIQ` service variables (`SUPABASE_KEY`, `SUPABASE_ANON_KEY`, Razorpay) - the backend references them, so it picks them up on redeploy. Also update the Supabase Edge Function secrets.
2. **Supabase Auth -> URL configuration**: Site URL `https://app.profileiq.co.in`; add the same plus the Railway web URL to Redirect URLs.
3. **Backend `ALLOWED_ORIGINS`** must include `https://app.profileiq.co.in`.
4. **Web service variables**: `NEXT_PUBLIC_API_URL` = backend URL (or a custom domain such as `api.profileiq.co.in`), `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`. These are baked in at build time - redeploy after any change.
5. **Razorpay**: add the new origin to the registered website/domain list; confirm the webhook still points at the Supabase Edge Function (unchanged).
6. Clear test invoices: `truncate invoices restart identity; alter sequence invoice_number_seq restart with 1;`
7. Switch Razorpay to **live** keys + live plan id.

## Cutover
1. Railway -> `desirable-trust` (web) -> Settings -> Networking -> add custom domain `app.profileiq.co.in` (move it off the `profileIQ` Streamlit service first; keep Streamlit reachable on its Railway URL as the fallback).
2. Update DNS CNAME as Railway instructs. Wait for the certificate.
3. Smoke test on a real Android and an iPhone: sign up -> email confirm -> log in -> score -> upgrade (UPI app handoff) -> Pro -> rewrite -> PDF/DOCX -> invoice email -> cancel.
4. Merge `migration` into `master` only after step 3 passes, then point Railway services at `master`.

## Rollback
Point `app.profileiq.co.in` back at the Streamlit service. Data is shared (same Supabase), so nothing needs migrating back. Keep Streamlit for two weeks.

## Security checklist (status)
- [x] Login token verified on every API call (Supabase `/auth/v1/user`), never trusted from the browser
- [x] Pro / free-scan limits enforced server-side; scan count updated with a conditional write (no double-spend)
- [x] Service-role key and Razorpay secret only on the server; no secrets in the browser bundle
- [x] CORS allow-list; docs/openapi disabled; HSTS, nosniff, no-store on API
- [x] Web: Content-Security-Policy, X-Frame-Options DENY, HSTS, Referrer-Policy, Permissions-Policy
- [x] Upload type/size checks; JSON bodies capped at 300 KB; per-user rate limits on AI, files, checkout, support
- [x] Payment confirmation checks the subscription belongs to the logged-in user; invoices always filtered by user id; invoice emails go only to the address on the invoice
- [x] User text is HTML-escaped in support emails; resume preview runs in a sandboxed iframe
- [ ] Rotate leaked keys (step 1 above)  - owner action
- [ ] Real-device payment test on the registered domain - after cutover step 1
- [ ] Rate limits are per server process (fine for one replica; move to Redis if you scale out)

## Admin page (/admin)
- URL: `https://app.profileiq.co.in/admin` (not linked anywhere, `noindex`).
- Only emails in the `ADMIN_EMAILS` variable on the **striking-harmony** (backend) service can sign in (default: `lakshmikanthkr3@gmail.com`; comma-separate to add more). Everyone else is refused by the server, not just hidden.
- Edits change `profiles.full_name / email / phone`, the Razorpay customer record, and the name stored with the login. Invoice and new-subscriber emails (Edge Function) and cancellation emails read the profile, so they pick up the corrected details. The user's login email is NOT changed.
