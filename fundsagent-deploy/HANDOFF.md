# HANDOFF — what's in this archive

> Hand-off note for the engineer deploying FundsAgent on Google Cloud.
> Read this first, then `DEPLOYMENT.md` for the full step-by-step.

## TL;DR — deploy in 5 commands

```bash
tar xzf fundsagent-deploy.tar.gz
cd fundsagent-deploy
gcloud config set project <YOUR_GCP_PROJECT_ID>
export CEREBRAS_API_KEY=csk-...        # ask the team for this
bash scripts/deploy.sh
```

That's it for the engine. The Cloud Run URL prints at the end.

For the frontend: open `frontend/index.html`, set `window.API_BASE_URL` to the
Cloud Run URL (one line at the top), upload to Lovable. Done.

## What you receive

```
fundsagent-deploy/
├── HANDOFF.md                  ← this file (read first)
├── DEPLOYMENT.md               ← full GCP deploy guide, 10 phases
├── README.md                   ← project overview, run/deploy
├── BRIEF.md                    ← hackathon context (criteria, sponsors)
│
├── fundsagent.py               ← the engine (~3500 lines, FastAPI single-file)
├── Dockerfile                  ← Cloud Run target
├── .gcloudignore               ← what gcloud uploads (147 KiB total)
│
├── scripts/
│   ├── deploy.sh               ← one-liner gcloud run deploy wrapper
│   └── smoke_health.sh         ← post-deploy sanity check
│
├── frontend/
│   ├── index.html              ← Lovable-ready, API-wired, 126 KB
│   └── README.md               ← frontend integration notes
│
├── PROJECT_SPEC.md             ← WHAT we built (GIVEN/WHEN/THEN)
├── DECISIONS.md                ← HOW: architecture, trade-offs, risks
├── ROADMAP.md                  ← 13 vertical slices, parallelization plan
├── ACCEPTANCE_CRITERIA.md      ← per-slice GIVEN/WHEN/THEN
├── CLAUDE.md                   ← agent operating instructions
│
└── grant-matcher.plugin        ← Cowork plugin (older deliverable, optional)
```

## What state the code is in

**Engine (`fundsagent.py`)**: production-ready prototype. Single file, all
dependencies pinned in `Dockerfile`. End-to-end flow tested live with
Cerebras Qwen 3 235B — total elapsed ~2.1 s from pasted pitchdeck to
generated dossier link. Includes a heuristic fallback when Cerebras is
unavailable, so the demo never blocks.

**Frontend (`frontend/index.html`)**: visually polished SubventionAI design,
adapter script appended that wires every piece to the live API. No build
step. Just static HTML — drop into any host (Lovable, Cloud Storage,
Vercel, plain Cloud Run).

**Spec docs**: complete and current as of 2026-04-25. Slice S1 (Cloud Run
deploy artifacts) is shipped — running `bash scripts/deploy.sh` is the
final step that closes AC-S1. Slices S2-S13 are pending (see `ROADMAP.md`).

## What you need to do (deploy day)

### 30 minutes — minimum viable demo URL

1. Create or pick a GCP project with billing enabled.
2. Enable APIs (one command, 2 min) — see `DEPLOYMENT.md §1.3`.
3. Push the Cerebras key to Secret Manager (`DEPLOYMENT.md §2.1`).
4. Create the runtime service account (`DEPLOYMENT.md §2.2`).
5. `bash scripts/deploy.sh` — first build is 2-3 min.
6. `bash scripts/smoke_health.sh <URL>` to confirm.
7. Open the URL in a browser — full demo flow works.

### 60 more minutes — Firestore + Lovable production frontend

8. Provision Firestore in Native mode (`DEPLOYMENT.md §4`).
9. Bind the runtime SA, mount secrets via `--update-secrets`
   (`DEPLOYMENT.md §3.3`).
10. Open `frontend/index.html`, set `window.API_BASE_URL` at the top.
11. Upload to Lovable as a single static page; publish.
12. Add CORS middleware to `fundsagent.py` (`DEPLOYMENT.md §8.2`),
    redeploy.

### Optional but recommended — full agentic pipeline

The remaining slices (`ROADMAP.md` S3-S9) bring in the SEDIA refresh job,
the French CSV ingestion via Gemini, the deep-dive Agent E. Each is
30-90 minutes of work. Run them in priority order if time allows; the
demo is fine without them as long as the static `GRANTS_DB` in
`fundsagent.py` is acceptable for the cohort you're showing.

## Secrets you need

- **`CEREBRAS_API_KEY`** — required. Ask the team. Format: `csk-...`.
  Free tier covers the hackathon.
- **`GEMINI_API_KEY`** — optional in the v0 demo. Required for
  multimodal PPTX fallback (slice S7) and deep-dive (slice S8/S9).
  Get one at https://aistudio.google.com → Get API key.
- **GCP service account JSON** — created during deploy in
  `DEPLOYMENT.md §2.2`. Stays inside GCP, never leaves.

## Reachability checks before going on stage

```bash
# 5 minutes before the pitch:
URL=$(gcloud run services describe fundsagent --region=europe-west1 --format='value(status.url)')

# Warm up
for i in 1 2 3; do curl -sS "$URL/api/health" >/dev/null; done

# Smoke
bash scripts/smoke_health.sh "$URL"

# Open in browser, run the GreenSilicon example, confirm < 30 s
open "$URL"
# (or open the Lovable URL if that is the demo URL)
```

If `smoke_health.sh` is green and you can see a dossier link in your browser
after pasting GreenSilicon, you are ready.

## If something breaks during the demo

1. Two browser tabs open before stage time: Lovable URL + raw Cloud Run URL.
   If Lovable hiccups, switch tab.
2. A cached video recording of a successful run saved locally. Last resort.
3. Phone hotspot tethered to the demo machine. Don't trust venue Wi-Fi.
4. Rollback: `gcloud run services update-traffic fundsagent --to-revisions <PREV>=100`.

## Contact

Slack channel: `#fintech-hackathon-fundsagent`
On-call dev: <name>, <phone>

---

Last updated: 2026-04-25 21:55 UTC.
