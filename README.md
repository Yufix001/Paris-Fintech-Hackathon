# Paris-Fintech-Hackathon

# Fundr — Paris Fintech Hackathon 2026

> **Track B2G · Non-dilutive funding access** · HEC Paris · 25–26 April 2026
> Built on **Cerebras** · **Google Cloud** · **Lovable**

> *"European founders are leaving tens of thousands of euros of public
> funding on the table. Nobody told them. Fundr does, in 30 seconds."*

---

## What we're building

Fundr is an autonomous AI agent that turns a startup pitch deck into a
**VC-grade non-dilutive funding dossier in under 30 seconds**.

The founder pastes pitch text or uploads a PDF/PPTX. The agent runs an
eight-step pipeline and streams every step live as Server-Sent Events:

1. **ParseAgent** — extracts company name, country/region, sectors, TRL,
   team, traction and funding ask. Uses Cerebras Qwen 3 235B for the LLM
   path; falls back to a regex heuristic when no API key is set.
2. **ClarifyAgent** — emits an `ask` event when critical fields are missing
   (e.g. country, TRL) so the user can fill them in before matching.
3. **MatchAgent** — scores the startup against **37 European public
   grants** (Bpifrance ADI, France 2030, Horizon Europe Cluster 1/4/5/6,
   EIC Accelerator/Pathfinder/Transition, ERC, MSCA, ADEME, regional
   FEDER programmes…). Rule-based engine with calibrated success-rate
   baselines per programme.
4. **ComboAgent** — finds cumulable combinations (e.g. FEDER IDF +
   Horizon EU, Bpifrance ADI + EIC Accelerator) respecting cumulability
   rules.
5. **PlanAgent** — synthesises a financing plan: total ask, expected
   non-dilutive amount, mix of grants/equity/debt, use-of-funds breakdown
   (R&D, hires, GTM, capex), disbursement timeline. Cerebras for the
   narrative, deterministic SVG rendering for the donut and stacked-bar
   charts.
6. **VCMatchAgent** — scans **370 European VCs** loaded from
   `data/vc_db.json` and surfaces the top 8 by sector, stage and geo
   fit. This complements the public-grant matching with dilutive-funding
   leads.
7. **DraftAgent** — writes a first version of the **Excellence section**
   for the top-matched grant, conditioned on the parsed pitch. Cerebras
   again — sub-second on stage.
8. **DossierAgent** — assembles a print-optimised A4 dossier and stores
   it in memory under a short id, returning a `/dossier/<id>` link.

The dossier is rendered server-side as a print-ready HTML page; the user
prints it to PDF from the browser.

### Out of scope for the hackathon

Auto-submission to public portals, e-signature, post-grant tracking,
multi-tenant for incubators (a single pitch slide only), and the full
Lovable production migration. The Lovable codebase under
`frontend-lovable/` is maintained in parallel but is not yet wired to the
deployed backend — the deployed UI is the vanilla single-file
`frontend/index.html`.

## Stack

| Layer | Tech | Status in code |
|---|---|---|
| Engine | FastAPI single-file (`fundsagent.py`, ~3.1k lines) | Live |
| Frontend (deployed) | Vanilla single-file `frontend/index.html`, served at `/` | Live |
| Frontend (Lovable) | Vite + React + shadcn/ui under `frontend-lovable/` | Separate codebase |
| LLM (hot path) | **Cerebras** Qwen 3 235B — parse, plan, draft | Live, ~0.5–0.7s per call |
| LLM (multimodal) | **Google** Gemini 3 Flash for visual pitch decks | Roadmap (slice S5) |
| Public grants DB | 37 grants embedded inline in `fundsagent.py` (`GRANTS_DB_JSON`) | Live |
| VC DB | 370 European VCs in `data/vc_db.json` | Live |
| Dossier store | In-memory dict, capped at 32 most recent dossiers | Live (Firestore = roadmap) |
| File extraction | `pdfplumber` / `pypdf` (PDF), `python-pptx` (PPTX) | Live |
| Deployment | **Google Cloud Run** `europe-west1`, 1 GiB / 1 CPU, `--min-instances=1` | Live |

Each sponsor does what it does best: Cerebras handles text in the demo's
hot path (sub-second per step), Gemini is reserved for visual pitchdeck
parsing in the next slice, Lovable is the production-frontend track in
parallel.

## How to run it

### 1 · Local

Python 3.10+ required.

```bash
git clone https://github.com/Than0316/Paris-Fintech-Hackathon.git
cd Paris-Fintech-Hackathon/fundsagent-deploy

pip install fastapi uvicorn httpx python-multipart pypdf python-pptx pdfplumber

# Optional — without it, the engine falls back to the regex heuristic
# parser (good enough for dev, not for the live demo).
export CEREBRAS_API_KEY=csk-...

python fundsagent.py
# → http://localhost:8000
```

In the browser:

1. Click **Example: GreenSilicon** (or paste your own pitch deck text /
   upload a PDF/PPTX).
2. Click **▶ Run agent**. The reasoning streams live in a vertical
   timeline.
3. On the dossier page, hit **Print** in the browser (Ctrl/Cmd + P) to
   save the A4 PDF.

### 2 · Docker

```bash
cd fundsagent-deploy
docker build -t fundr .
docker run -p 8000:8000 -e CEREBRAS_API_KEY=csk-... fundr
# → http://localhost:8000
```

### 3 · Google Cloud Run

`gcloud` authenticated, project set, Cloud Run + Cloud Build APIs enabled.

```bash
cd fundsagent-deploy
export CEREBRAS_API_KEY=csk-...
bash scripts/deploy.sh
```

The script wraps `gcloud run deploy --source .` with the right flags
(`europe-west1`, `--allow-unauthenticated`, `--min-instances=1`, 1 GiB
/ 1 CPU, concurrency 40). Override defaults via env:

```bash
PROJECT_ID=my-proj REGION=europe-west1 MIN_INSTANCES=1 \
  bash scripts/deploy.sh

bash scripts/deploy.sh --dry-run   # print the gcloud command, do not run
```

Smoke-test once deployed:

```bash
bash scripts/smoke_health.sh https://fundr-XXXX-ew.a.run.app
```

It checks `/api/health` returns `status: ok`, `grants_loaded ≥ 37`, and
warns if Cerebras is not configured.

### 4 · Lovable frontend (dev only)

```bash
cd fundsagent-deploy/frontend-lovable
npm install
npm run dev          # http://localhost:5173
npm run test         # vitest
npm run build
```

It targets the Python backend via `VITE_API_URL` (defaults to
`http://localhost:8000`). Maintained as a separate codebase — the
deployed UI is `frontend/index.html` served by FastAPI.

## API endpoints

| Method | Path | Returns |
|---|---|---|
| `GET`  | `/` | Single-page UI (`frontend/index.html`) |
| `POST` | `/api/agent/run` | SSE stream: `thinking`, `parsed`, `ask`, `matched`, `combos`, `plan`, `vc_matches`, `draft`, `dossier`, `done`, `error` |
| `POST` | `/api/match` | One-shot match: send a parsed pitchdeck JSON, get back ranked grants |
| `POST` | `/api/upload` | Upload PDF/PPTX, returns extracted text |
| `GET`  | `/dossier/{id}` | Printable A4 dossier (HTML) |
| `GET`  | `/api/dossier/{id}` | Same dossier as JSON |
| `GET`  | `/api/grants` | The 37-grant DB |
| `GET`  | `/api/health` | `{status, grants_loaded, vcs_loaded, cerebras_configured}` |
| `GET`  | `/static/{filename}` | Static assets (logo, demo deck) |

## Repo layout

```
.
├── README.md                ← this file
├── LICENSE                  ← MIT
└── fundsagent-deploy/       ← the product (folder name preserved; brand is Fundr)
    ├── fundsagent.py            FastAPI single-file engine + 37-grant embed
    ├── data/vc_db.json          370 European VCs for VCMatchAgent
    ├── frontend/index.html      vanilla single-file UI served at /
    ├── frontend-lovable/        Vite + React + shadcn dev frontend (separate)
    ├── scripts/                 deploy.sh, smoke_health.sh
    ├── Dockerfile
    ├── PROJECT_SPEC.md          the WHAT — promise, persona, GIVEN/WHEN/THEN
    ├── DECISIONS.md             the HOW — architecture, stack, trade-offs
    ├── ROADMAP.md               13 vertical slices
    ├── ACCEPTANCE_CRITERIA.md   per-slice tests
    ├── DEPLOYMENT.md            Cloud Run hardening guide
    ├── BRIEF.md                 hackathon brief
    ├── HANDOFF.md               handover notes
    └── CLAUDE.md                operating principles
```

The folder is still `fundsagent-deploy/` and the engine file
`fundsagent.py` — only the product brand was renamed to **Fundr**.
Renaming the filesystem is a separate, larger commit.

## Workflow (Hg Capital — Agentic Coding)

`/refine → /plan → /breakdown → /execute → /review`. Vertical slices
(UI + logic + data, end-to-end), separate reviewer agent. Slice plan in
`fundsagent-deploy/ROADMAP.md`.

## Team

5 people — 2 devs + 3 design / slides / pitch.

## License

[MIT](LICENSE).
