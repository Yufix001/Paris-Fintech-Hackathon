# Frontend — SubventionAI / FundsAgent

Static HTML page (`index.html`) wired to the FundsAgent FastAPI backend
running on Cloud Run.

## Configure the API endpoint

The page reads `window.API_BASE_URL` for every fetch. Two ways to set it:

### Option A — Lovable env var (recommended for production)

In the Lovable project settings, add an environment variable:

```
NEXT_PUBLIC_API_BASE_URL = https://fundsagent-XXXX-ew.a.run.app
```

Then add a tiny inline script at the top of `index.html` (before the adapter
script at the bottom):

```html
<script>
  window.API_BASE_URL = "%NEXT_PUBLIC_API_BASE_URL%";   // Lovable substitutes
</script>
```

(Lovable replaces `%NEXT_PUBLIC_API_BASE_URL%` at build time. If your hosting
does not support env-var substitution, see Option B.)

### Option B — Hardcode after deploy

Open `index.html`, search for `CHANGE-ME.run.app` near the bottom of the file,
replace with your actual Cloud Run URL.

## Local development

```bash
# 1. Boot the FastAPI backend
cd ..
python3 fundsagent.py
# → http://localhost:8000

# 2. Serve the frontend (any static server works)
cd frontend
python3 -m http.server 9090
# → http://localhost:9090/index.html
```

The adapter detects `localhost` and points at `location.origin` by default;
if you serve the frontend on a different port from the API, set
`window.API_BASE_URL = "http://localhost:8000"` before the adapter script.

## What the adapter does

The original `subvention_ai_demo.html` is a static 4-step wizard with
`simulateUpload()` mocking the agent flow. The adapter at the bottom of the
file (search for `FundsAgent API adapter`):

- Adds a textarea + 3 example pitchdecks + a real PDF/PPTX upload zone on step 1.
- Replaces `simulateUpload()` with a real call to `POST /api/agent/run` (SSE).
- Maps the 8 agent event types to the existing 4 stream sub-steps.
- Populates step 3 (diagnostic) panels dynamically from the parsed pitchdeck.
- Replaces the mocked donut chart with the real `use_of_funds` breakdown.
- Replaces the mocked grants list with the real matched programmes.
- Adds a *Download dossier PDF* button on step 4.
- Probes `/api/health` on load and warns in the console if the backend is unreachable.

The original visual design is **untouched** — the adapter only injects new
behaviour and replaces dynamic data.

## Backend contract consumed

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Boot check (called automatically) |
| `POST` | `/api/agent/run` | SSE agent stream (the main flow) |
| `POST` | `/api/upload` | PDF/PPTX text extraction (file upload button) |
| `GET` | `/dossier/{id}?print=1` | Printable A4 dossier (PDF download) |

## CORS

The backend must allow this frontend's origin. See `DEPLOYMENT.md §8.2`.
For Lovable previews and production, the regex
`https://.*\.lovable\.(app|dev|project\.com)` is whitelisted.
