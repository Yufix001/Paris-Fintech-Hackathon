# FundsAgent

> **Track B2G — Paris Fintech Hackathon 2026** · Cerebras · Google Cloud · Lovable

Autonomous AI agent that reads a startup pitchdeck and produces a VC-grade
non-dilutive funding dossier — eligibility match against 37 European public
grants, use-of-funds breakdown, financing plan, draft of the Excellence
section, A4 printable PDF — in under 30 seconds.

> *"Votre startup a droit à des dizaines de milliers d'euros de financement
> public. Personne ne vous l'a dit. FundsAgent le fait en 30 secondes."*

## Live demo

- **Production URL** — `https://fundsagent-<hash>-ew.a.run.app` *(populated after first deploy)*
- **Pitch deck** — `pitch-deck.pdf` *(slice S13)*
- **Architecture** — see [DECISIONS.md](DECISIONS.md)
- **Spec** — see [PROJECT_SPEC.md](PROJECT_SPEC.md)
- **Roadmap** — see [ROADMAP.md](ROADMAP.md)

## Run it locally

```bash
pip install fastapi uvicorn httpx python-multipart pypdf python-pptx pdfplumber
export CEREBRAS_API_KEY=csk-...      # optional — heuristic fallback otherwise
export GEMINI_API_KEY=...            # optional — used by S4/S7/S8
python fundsagent.py
# → http://localhost:8000
```

Click **Example: GreenSilicon** then **▶ Run agent**. The agent streams its
reasoning live (parse → match → plan → draft → dossier). Click **Download PDF**
on the dossier to get an A4 file ready to send to investors.

## Deploy to Cloud Run

One-line deploy assuming `gcloud` is authenticated and a project is set:

```bash
export CEREBRAS_API_KEY=csk-...
bash scripts/deploy.sh
```

The script wraps `gcloud run deploy --source .` with the right flags
(`--min-instances=1`, `--allow-unauthenticated`, `europe-west1`, 1 GiB / 1 CPU).
Override defaults via env vars:

```bash
PROJECT_ID=my-project REGION=europe-west1 MIN_INSTANCES=1 \
  bash scripts/deploy.sh
```

Dry-run (prints the gcloud command, does not run):

```bash
bash scripts/deploy.sh --dry-run
```

After deploy, validate the URL is healthy:

```bash
bash scripts/smoke_health.sh https://fundsagent-XXXX-ew.a.run.app
```

The slice S12 will replace this with a full end-to-end smoke test (agent run +
dossier reachability).

## Architecture in one paragraph

`fundsagent.py` is a single-file FastAPI engine that exposes
`POST /api/agent/run` (Server-Sent Events streaming the agent's steps),
`GET /dossier/<id>` (printable A4 page), and a static UI at `/`. The matcher
is rule-based against 37 curated grants; Cerebras Qwen 3 235B handles
parsing, financing-plan synthesis, and Excellence drafting in the user-facing
hot path (sub-3-second budget). Vertex AI Gemini 3 covers nightly batch data
refresh and on-demand deep-dive personalization. State lives in Firestore;
deployed on Cloud Run. See [DECISIONS.md](DECISIONS.md) for trade-offs and
[ROADMAP.md](ROADMAP.md) for the slice-by-slice build plan.

## Project files

| Doc | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Operating principles + artifact inventory. Read first. |
| [`PROJECT_SPEC.md`](PROJECT_SPEC.md) | The WHAT — product promise, persona, journey, GIVEN/WHEN/THEN. |
| [`DECISIONS.md`](DECISIONS.md) | The HOW — architecture, stack, trade-offs, risks. |
| [`ROADMAP.md`](ROADMAP.md) | 13 vertical slices, parallelized across 2 devs + 3 designers. |
| [`ACCEPTANCE_CRITERIA.md`](ACCEPTANCE_CRITERIA.md) | Per-slice GIVEN/WHEN/THEN + manual tests. |
| [`BRIEF.md`](BRIEF.md) | Cleaned hackathon brief (criteria, sponsors, format). |

## License

MIT.
