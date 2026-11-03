# ProfileIQ API (FastAPI)

Phase 1 of the Streamlit → Next.js migration. Runs beside the existing app; shares the same Supabase, Razorpay and Resend.

## Endpoints (all but /health need `Authorization: Bearer <Supabase login token>`)
| Method | Path | What it does |
| --- | --- | --- |
| GET | /health | Liveness check |
| GET | /v1/me | Plan, free scans left |
| GET | /v1/templates | Resume format names |
| POST | /v1/score | multipart `resume` (+ `jd`): ATS score, keywords, suggestions. Free users: 3 scans per 30 days |
| POST | /v1/rewrite | multipart `resume` + `jd`: AI rewrite + after-score. Pro only |
| POST | /v1/fresher | JSON `{profile, jd}`: fresher resume. Pro only |
| POST | /v1/resume/file | JSON `{data, template, format: pdf\|docx}`: file download. Pro only |
| POST | /v1/resume/preview | JSON `{data, template}`: HTML preview. Pro only |

## Railway variables
`ANTHROPIC_API_KEY`, `SUPABASE_KEY` (service-role, secret), `SUPABASE_ANON_KEY`, `SUPABASE_URL`, `ALLOWED_ORIGINS` (comma-separated web app addresses), optional `CLAUDE_MODEL`, `MAX_UPLOAD_MB`, `AI_CALLS_PER_WINDOW`, `AI_WINDOW_SECONDS`.

## Run locally
    pip install -r requirements.txt pytest httpx
    SUPABASE_KEY=x python -m pytest tests
    uvicorn app.main:app --reload

## Deploy on Railway
New service from this repo, **Root Directory = `backend`**, branch `migration` until cutover.
