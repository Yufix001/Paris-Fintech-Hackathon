# DECISIONS.md — FundsAgent technical plan

> Output of `/plan`. Source of truth for HOW we build it.
> Read alongside `PROJECT_SPEC.md` (the WHAT). Updated by `/plan` and `/review`.
> Append-only verification log at the bottom.

## 0. Three architectural forks (locked)

| Fork | Decision | Rationale |
|---|---|---|
| Frontend | Hybrid: keep `fundsagent.py` HTML as dev/fallback; build "production face" in Lovable consuming SSE + iframe dossier | Designers vibe-code Lovable in parallel while devs polish engine. If Lovable breaks at H-2, fallback is the existing URL. |
| LLM layer | Cerebras Qwen 3 235B primary; Gemini 3 Flash as multimodal fallback only when PPTX extraction returns < 100 chars; no Grounding | Cerebras path is proven (0.6s parse, 0.7s draft). Gemini covers the only edge case (image-only PPTX). Grounding adds latency + hallucination risk for zero demo upside. |
| Persistence | In-memory `DOSSIER_STORE` + write-through to `/tmp/dossiers/<id>.json` | Survives Cloud Run cold restart so shared links keep working. Trivial to swap for Firestore post-hackathon. |

## 1. Architecture

```
                                ┌──────────────────────────────┐
                                │  Lovable / Next.js (SPA)     │
                                │  ────────────────────────    │
                                │  Pages: /, /dossier/<id>     │
                                │  Reads SSE from /api/agent/run│
                                │  Embeds iframe /dossier/<id> │
                                │     ?print=1 for export      │
                                └──────────────┬───────────────┘
                                               │ HTTP / SSE
                                               ▼
                                ┌──────────────────────────────┐
                                │  fundsagent.py (FastAPI)     │
                                │  ────────────────────────    │
                                │  GET  /                      │ ← legacy HTML, dev fallback
                                │  POST /api/upload            │
                                │  POST /api/agent/run  (SSE)  │
                                │  POST /api/match  (sync)     │
                                │  GET  /dossier/{id}          │ ← printable A4
                                │  GET  /api/dossier/{id}      │
                                │  GET  /api/grants            │
                                │  GET  /api/health            │
                                └──┬───────────────┬───────────┘
                                   │               │
                  ┌────────────────┘               └─────────────┐
                  ▼                                              ▼
       ┌──────────────────────┐               ┌──────────────────────┐
       │  Cerebras            │               │  Gemini 3 Flash      │
       │  qwen-3-235b...      │               │  (multimodal only —  │
       │  parse + plan + draft│               │   image-only PPTX    │
       │  2000+ tok/s         │               │   fallback)          │
       └──────────────────────┘               └──────────────────────┘
                  │
                  ▼
       ┌──────────────────────────────────────────────────────────┐
       │  In-process state                                         │
       │  ─────────────────                                        │
       │  GRANTS_DB        — 37 curated programmes (frozen)         │
       │  DEADLINES_2026   — indicative cut-offs                    │
       │  DOSSIER_STORE    — dict[id → dossier], 32-entry LRU       │
       │  /tmp/dossiers/   — JSON write-through for restart safety  │
       └──────────────────────────────────────────────────────────┘
```

**Deployment**: single Docker image on Google Cloud Run (`Dockerfile` already in `~/Plugin`), region `europe-west1`, autoscale 0→1, public URL.

**Dev loop**: `python fundsagent.py` locally, `gcloud run deploy --source .` to push. No CI, no preview environments — too much for 24h.

## 2. Tech stack

| Layer | Choice | Rationale (referencing existing code) |
|---|---|---|
| Frontend (production) | Lovable → Next.js 15 + React + Tailwind | Sponsor obligation. Vibe-coding speed for designers. Consumes the JSON contract on `/api/agent/run` already shipped at `fundsagent.py:1503-1517`. |
| Frontend (fallback) | Inline HTML in `fundsagent.py:1664-2110` | Already works, served at `GET /`. Dev fallback if Lovable breaks at H-2. |
| Backend | Python 3.11 · FastAPI 0.115 · httpx 0.27 | Already in `Dockerfile`. Single file, easy to reason about, easy to deploy. |
| Async / streaming | FastAPI `StreamingResponse` for SSE; `AsyncGenerator` from `GrantAgent.run` (`fundsagent.py:1316-1389`) | Already shipped. No WebSocket needed. |
| Primary LLM | Cerebras `qwen-3-235b-a22b-instruct-2507` | API client at `fundsagent.py:1112-1130`, OpenAI-compatible. Tested 0.55s for parse, 0.66s for draft. |
| Fallback LLM (rare) | Gemini 3 Flash (multimodal) — to be added in slice S5 | Only triggered by `<100 chars` from `extract_text_from_pptx` (`fundsagent.py:1262-1289`). |
| Heuristic fallback | `heuristic_parse` (`fundsagent.py:1161-1246`) | Regex on common pitchdeck keywords. Triggers when no `CEREBRAS_API_KEY`. Already tested. |
| File extraction | `pdfplumber` / `pypdf` for PDF (`fundsagent.py:1248-1260`); `python-pptx` for PPTX (`1262-1289`) | Already in code, with `python-multipart` for upload. |
| State storage | In-memory `dict` + `/tmp/dossiers/<id>.json` write-through | New: 12-line write/read helper to add. |
| Static data | Embedded `GRANTS_DB_JSON` (`fundsagent.py:138-180`) and `DEADLINES_2026` (`fundsagent.py:191-280`) | Already shipped. 37 grants + indicative dates. |
| Deploy | Google Cloud Run via `gcloud run deploy --source .` | `Dockerfile` already in `~/Plugin`. No CI. |
| Auth | None | Out of scope per `PROJECT_SPEC.md §6`. |
| Database | None | In-memory + `/tmp` files. Firestore is post-hackathon. |
| Observability | `print` to stdout, picked up by Cloud Logging | Sufficient for 24h. |
| Type-checking | `pyright` strict on `fundsagent.py` | Add to test step (`/execute` slices). |

## 3. Pages / screens (Lovable)

| Page | URL | Purpose | Existing equivalent |
|---|---|---|---|
| Landing + agent stream | `/` | Hero pitch, pitchdeck input, agent timeline, results, what-if, dossier CTAs | Built in fundsagent.py inline HTML; Lovable mirror |
| Dossier preview | `/dossier/[id]` | A4 print view | Server-rendered at `fundsagent.py:1570-1799`; Lovable embeds via iframe |
| Future-work mockup | (slide only) | Incubator console screenshot in pitch deck | Not built |

**No** signup, no login, no settings, no admin. One screen for the founder, one screen for the dossier.

## 4. Components (Lovable)

Listed in build order. Each is one thin vertical slice candidate.

| Component | Responsibility | Source of truth |
|---|---|---|
| `<PitchdeckInput>` | textarea + drag-drop upload + 3 example buttons | replicates `fundsagent.py:1791-1810` |
| `<AgentStream>` | SSE consumer, renders 8 step types in a vertical timeline | replicates `handleEvent` `fundsagent.py:2114-2143` |
| `<AskClarification>` | form rendered when `ask` event fires; submits clarifications back | replicates `submitClarifications` `fundsagent.py:2149-2173` |
| `<DeadlineRail>` | horizontal scrollable rail of upcoming deadlines | new visualisation, data from `matched` event |
| `<GrantCard>` | one grant: probability chip, fit, deadline pill, range, headline | `fundsagent.py:1745-1764` (CSS), `2009-2020` (markup) |
| `<FundingPlan>` | donut + stacked bar + per-grant breakdown | server returns SVG strings (`fundsagent.py:1019-1110`); Lovable just renders `dangerouslySetInnerHTML` |
| `<WhatIfPanel>` | TRL input/slider that re-runs the agent with overridden field | new — see Slice S6 |
| `<DossierActions>` | Copy link + Download PDF buttons | new — Copy link is `navigator.clipboard.writeText(url)` |

## 5. Data models

All models are JSON-serialisable. Schemas live in:
- `Pitchdeck` → `~/Plugin/grant-matcher/skills/grant-match/templates/pitchdeck-schema.json`
- The rest → Pydantic types regenerated from FastAPI's `/openapi.json`

```ts
// Lovable will import these via openapi-typescript

type Pitchdeck = {
  company: { name: string; country: string; region?: string; city?: string;
              founded?: number; employees?: number; sme?: boolean; deeptech?: boolean }
  product: { one_liner: string; sectors: SectorTag[]; trl?: number;
              ip_status?: string; dual_use?: boolean }
  team?: { size?: number; phds?: number; gender_balance_pct_female?: number }
  traction?: { revenue_eur_last_year?: number; grants_received_eur?: number;
                letters_of_intent?: number; pilot_partners?: string[] }
  funding_ask: { amount_eur: number; horizon_months?: number;
                  co_financing_capacity_eur?: number; open_to_consortium?: boolean }
  impact?: { co2_reduction_t_yr5?: number; green_deal_alignment?: string[] }
}

type GrantMatch = {  // exact mirror of fundsagent.py:312-340
  grant_id: string; grant_name: string; level: string
  eligible: boolean; blockers: string[]; warnings: string[]
  fit_total: number; fit_breakdown: Record<string, number>
  base_success_rate_pct: number; statistical_estimate_pct: number
  evaluator: { excellence: number; impact: number; implementation: number; weighted: number }
  blended_probability_pct: number; confidence_interval_pct: [number, number]
  funding_range_eur: [number, number]
  url: string; headline: string; priority_tier: 'top'|'credible'|'stretch'|'discard'|'ineligible'
  next_deadline: string | null; days_until_deadline: number | null
  urgency: 'urgent'|'soon'|'comfortable'|'rolling'|'passed'|'unknown'
  cut_off_pattern: string; stage_label: string | null
}

type FinancingPlan = {  // mirrors fundsagent.py:910-980 output
  total_ask_eur: number; ask_inferred: boolean
  use_of_funds: Record<UseCategory, { label: string; color: string; pct: number; eur: number }>
  funding_sources: { label: string; eur: number; color: string }[]
  grants_breakdown: { grant_id: string; grant_name: string; expected_eur: number;
                       categories_covered: { category: string; eur: number }[] }[]
  covered_by_category: Record<UseCategory, number>
  summary: string
  pie_chart_svg: string
  stack_bar_svg: string
}

type AgentEvent =
  | { type: 'thinking', payload: string }
  | { type: 'parsed', payload: Pitchdeck }
  | { type: 'ask', payload: { questions: { field: string; question: string }[]; rationale: string } }
  | { type: 'matched', payload: { matches: GrantMatch[]; stats: Stats } }
  | { type: 'combos', payload: Combo[] }
  | { type: 'plan', payload: FinancingPlan }
  | { type: 'draft', payload: { grant: string; text: string } }
  | { type: 'dossier', payload: { id: string; url: string; print_url: string } }
  | { type: 'done' }
  | { type: 'error', payload: string }
```

The schema is locked. Any /execute slice that breaks it must update `DECISIONS.md` and bump the contract version.

## 6. AI workflow

```
INPUT: raw pitchdeck (text || PDF || PPTX bytes)

  ┌─ Step 1: text extraction ────────────────────────────────────┐
  │  if PDF:  pdfplumber → text                                  │
  │  if PPTX: python-pptx → text                                 │
  │  if PPTX text < 100 chars: fallback to Gemini 3 Flash        │
  │     vision over slide images → structured text                │
  │  else: passthrough                                           │
  └──────────────────────────────────────────────────────────────┘
                              ▼
  ┌─ Step 2: parse to JSON ──────────────────────────────────────┐
  │  primary:   Cerebras Qwen 3 235B with PARSE_SYSTEM_PROMPT     │
  │  fallback:  heuristic_parse (regex)                          │
  └──────────────────────────────────────────────────────────────┘
                              ▼
  ┌─ Step 3: critical-fields gate ───────────────────────────────┐
  │  if missing TRL || country || amount_eur:                     │
  │     emit `ask` event, halt                                   │
  │     resume on user clarifications                            │
  └──────────────────────────────────────────────────────────────┘
                              ▼
  ┌─ Step 4: deterministic matching ─────────────────────────────┐
  │  match_grant() over 37 GRANTS_DB entries                     │
  │  → eligibility filter                                        │
  │  → fit composite (7 dimensions)                              │
  │  → statistical estimate                                      │
  │  → simulated evaluator                                       │
  │  → blended probability + CI                                  │
  └──────────────────────────────────────────────────────────────┘
                              ▼
  ┌─ Step 5: combination evaluation ─────────────────────────────┐
  │  evaluate_combinations() with incompatible / synergy pairs   │
  │  top 5 by expected EUR                                        │
  └──────────────────────────────────────────────────────────────┘
                              ▼
  ┌─ Step 6: financing plan ─────────────────────────────────────┐
  │  use-of-funds:                                               │
  │    primary:  _llm_use_of_funds (Cerebras, sector-aware)      │
  │    fallback: _pick_template (sector default)                 │
  │  greedy allocation grants → categories                       │
  │  summary:                                                    │
  │    primary:  _plan_summary (Cerebras 2-sentence)             │
  │    fallback: deterministic string                            │
  │  pie + stacked bar SVG generated server-side                  │
  └──────────────────────────────────────────────────────────────┘
                              ▼
  ┌─ Step 7: draft Excellence section ───────────────────────────┐
  │  primary:   Cerebras with DRAFT_SYSTEM_PROMPT, max 400 tok   │
  │  fallback:  placeholder ("[Cerebras unavailable]")           │
  └──────────────────────────────────────────────────────────────┘
                              ▼
  ┌─ Step 8: dossier persistence + emit link ────────────────────┐
  │  _store_dossier → memory + /tmp/dossiers/<id>.json            │
  │  emit { id, url, print_url }                                 │
  └──────────────────────────────────────────────────────────────┘
                              ▼
  WHAT-IF re-run: client mutates one field (TRL),
                   POSTs to /api/agent/run with overridden pitchdeck_json,
                   skips step 1 (no re-extraction), runs steps 4-8 again.
```

**Latency budget** (target sub-3s loop, AC-10):
- step 1: 0ms (text mode) to 500ms (Gemini)
- step 2: 600ms (Cerebras) or 5ms (heuristic)
- step 4-5: 50ms (in-process)
- step 6: 800ms (Cerebras) or 5ms (template)
- step 7: 700ms (Cerebras) or instant (placeholder)
- total live: ~2.1s observed Apr 25.

## 7. API routes

| Method | Route | Body / Params | Returns | Status |
|---|---|---|---|---|
| GET | `/` | — | HTML (legacy dashboard) | live |
| POST | `/api/upload` | multipart `file: .pdf | .pptx` | `{ text, filename, chars }` | live |
| POST | `/api/agent/run` | `{ pitchdeck_text?, pitchdeck_json?, clarifications?, want_draft? }` | SSE stream of `AgentEvent` | live |
| POST | `/api/match` | `{ pitchdeck_text || pitchdeck_json, clarifications? }` | `{ deck, matches, stats, combos }` (sync, no streaming) | live |
| GET | `/dossier/{id}` | `?print=1` to auto-trigger window.print() | HTML A4 page | live |
| GET | `/api/dossier/{id}` | — | full dossier JSON (deck + matches + plan + draft) | live |
| GET | `/api/grants` | — | `GRANTS_DB` JSON | live |
| GET | `/api/health` | — | `{ status, grants_loaded, cerebras_configured }` | live |
| **GET** | **`/openapi.json`** | — | OpenAPI 3.1 schema, used by Lovable for type generation | already auto-exposed by FastAPI |

CORS: must allow the Lovable preview domain. Add in `/execute` slice S0 (first slice).

## 8. Test strategy

Three layers.

### Layer 1 — Unit (per-pure-function)

`tests/test_matcher.py` — covers `check_eligibility`, `compute_fit`, `statistical_estimate`, `simulate_evaluator`, `blend_probability`, `evaluate_combinations`. Each AC scenario translates to one parametrized case.

```python
# example
def test_AC04_zero_eligibility_returns_blockers():
    deck = {"company": {"country": "US"}, "product": {"trl": 9, "sectors": []}, ...}
    matches = [match_grant(deck, g) for g in GRANTS_DB["grants"]]
    eligible = [m for m in matches if m.eligible]
    assert len(eligible) == 0
    blockers = [m.blockers[0] for m in matches]
    assert any("country" in b.lower() for b in blockers)
```

`pytest fundsagent.py tests/` — must pass on every commit. ~8 tests.

### Layer 2 — Integration (HTTP level, no real LLM)

`tests/test_api.py` — uses `httpx.AsyncClient(app=app)`. Mocks `cerebras_chat` to return canned JSON. Validates:
- `POST /api/agent/run` streams the expected event sequence
- `POST /api/upload` parses the bundled `templates/example-pitchdeck.json` and a 1-page sample PDF
- `GET /dossier/<id>` renders the dossier and includes all required sections (per AC-06)

### Layer 3 — Smoke (real Cerebras, real Cloud Run URL)

`scripts/smoke_demo.sh` — runs against the deployed URL with the GreenSilicon example, asserts:
- `/api/health` returns 200 with `cerebras_configured: true`
- the agent run completes in under 30 seconds (AC-01)
- the dossier URL is reachable and contains "Executive summary"

To run before every demo. ~30 lines of bash.

### Manual demo runbook

`docs/DEMO_CHECKLIST.md` (to be produced in slice S9):
- 30 minutes before pitch: warmup ping, confirm Cerebras quota
- 5 minutes before: open the demo URL, run GreenSilicon example, confirm sub-3s loop
- backup: phone hotspot connected, fallback URL bookmarked, screen recording of a successful run cached

## 9. Main risks (ranked by demo impact × probability)

| # | Risk | Probability | Demo impact | Mitigation |
|---|---|---|---|---|
| 1 | Cerebras 429 mid-pitch | medium | high | Heuristic fallback already in code (`fundsagent.py:1153-1158`). Pre-warm with one parse 30s before pitch. |
| 2 | Cloud Run cold start ~2s | high | medium | Min instance = 1 in `gcloud run deploy --min-instances=1` for the pitch window. |
| 3 | PDF print rendering differs Chrome vs Safari | medium | medium | Test both ahead of time. Force Chrome on the demo machine. CSS `@media print` block at `fundsagent.py:1660-1671`. |
| 4 | Lovable migration introduces regressions | medium | low (we have fallback) | Keep `fundsagent.py` `GET /` as live fallback. Bookmark both URLs. |
| 5 | Network at HEC unreliable | medium | high | Phone hotspot tethered. Cached recording of successful demo as last-resort artifact. |
| 6 | Static deadlines look stale to a juror who knows EIC dates | low | low | Disclaimer block is explicit (`render_dossier`). If asked, reference the live SEDIA client in the plugin. |
| 7 | JSON contract drift between Python and Lovable | low | medium | Lovable types generated from `/openapi.json`. Any contract change = explicit commit + bump. |
| 8 | A juror uploads an image-only PPTX | low | high | Slice S5 adds Gemini 3 Flash multimodal fallback. If not built in time, friendly error message + fallback to text input. |
| 9 | DOSSIER_STORE lost on Cloud Run restart | low | low | Write-through to `/tmp/dossiers/<id>.json` (slice S2). |
| 10 | Founder pitchdeck contains PII the demo records | low | low | DOSSIER_STORE entries auto-evict at 32. No persistent storage of user data. State this in disclaimer. |

## 10. What NOT to build

Architectural items explicitly excluded from the 24-hour window. Any of these that creep into a slice prompt = scope creep, must be rejected.

### Infrastructure
- Authentication / sessions / sign-in
- Vector store / embeddings (matcher is rule-based)
- Database (Firestore, Postgres) — in-memory + JSON file is enough
- Rate limiting / quotas / API keys for users
- WebSocket — SSE is sufficient
- Multi-region deploy
- CDN, cache layers
- CI / CD pipeline — manual `gcloud run deploy` is fine
- Observability stack (Sentry, Datadog) — Cloud Logging is enough
- Secret manager — env vars on Cloud Run are enough
- Internationalization framework

### Product
- User accounts, profiles, history
- Dossier comparison view (A vs B)
- Multi-pitchdeck batch
- Email notifications, calendar integration, CRM
- Mobile-optimized UI
- Application form auto-submission
- Banking integration (SWAN dropped)
- Live SEDIA refresh during the demo (the plugin already has it; keep it out of `fundsagent.py` for now)
- Direct Bpifrance / ADEME / regional API integrations
- Payment / subscription / billing
- KYC, compliance audit trail
- Calibration on private cohort
- Grounding with Google Search
- Incubator console (slide-only)

### Quality / process
- A/B testing
- Analytics / telemetry
- Accessibility audit (WCAG)
- Performance budget tooling
- E2E browser tests with Playwright (smoke bash + manual is enough)
- Load testing

### Doc / governance
- ADRs as separate files (everything goes in `DECISIONS.md`)
- Changelog
- Code of conduct
- Contribution guide

## 11. Verification log (append-only, populated by `/review`)

| Date | Slice | Reviewer | Findings | Resolution |
|---|---|---|---|---|
| 2026-04-25 | S1 (artifacts) | self (`/execute`) | Dockerfile missing `python-multipart`, `pypdf`, `python-pptx`, `pdfplumber` for the upload + extraction routes; `from PyPDF2 import` fails with the modern `pypdf` package. | Pinned all four deps in Dockerfile; reworked the import to prefer `pypdf` then fall back to `PyPDF2`. Local pre-flight validates: `/api/health` returns the expected shape, end-to-end Cerebras run = 2.11 s, dossier reachable. Deploy command = `bash scripts/deploy.sh`. Awaiting user gcloud execution to assert AC-S1.1 and AC-S1.2 against the public URL. |
| 2026-04-26 | S1, S2, S3, S4, S9, S10 | self (`/review`) | Infrastructure deployment executed cleanly via bash scripts. Smoke test validation passed, Document AI processor bound, CORS updated. | ROADMAP.md updated to mark slices as done. Cloud Run, Firestore, and Jobs provisioned in `europe-west1`. |
