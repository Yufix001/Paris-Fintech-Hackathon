# CLAUDE.md — agent operating instructions

> Read this file BEFORE acting on any request. It is the foundational context
> for every slice. Update it after any meaningful change.

## Project identity

**FundsAgent** — autonomous AI agent that reads a startup pitchdeck and
produces a VC-grade non-dilutive funding dossier (37+ public grants matched,
use-of-funds breakdown, financing plan, draft Excellence section, printable
A4 PDF). Track **B2G** for the Paris Fintech Hackathon 2026 (HEC Paris,
24h, Apr 25-26).

**Why fintech.** Financial inclusion (founders without cabinet access),
RegTech (cumulability rules encoded), credible VC dossier (use-of-funds +
sources of funds is the language investors speak).

**Sponsors to integrate (all three or AI Integration score suffers).**

- **Cerebras** — Qwen 3 235B / Llama, 2000+ tok/s. Wow factor. Used for
  pitchdeck parsing, financing plan synthesis, draft Excellence section.
- **Google Cloud** — Cloud Run for deployment, Gemini API for multimodal
  fallback (PPTX/PDF visual parsing — Cerebras is text-only), Grounding
  with Google Search to refresh grant conditions. AI Studio Build for
  initial scaffolding, Firebase Auth + Firestore for stateful prod.
- **Lovable** — production frontend. The single-file Python is the engine.

## Operating principles (verbatim)

1. Context is everything. Always read CLAUDE.md, PROJECT_SPEC.md,
   ROADMAP.md, ACCEPTANCE_CRITERIA.md, and DECISIONS.md before acting.
2. Treat every task as a thin vertical slice delivering user-visible value
   end-to-end.
3. Do not build horizontal layers in isolation.
4. Do not modify unrelated files.
5. Do not build future slices unless explicitly asked.
6. Every unit of work must have clear acceptance criteria.
7. Write tests or manual test plans before implementation.
8. Run lint, format, typecheck, and tests after changes.
9. Verify end-to-end before claiming done.
10. Provide evidence: screenshot, logs, or exact test output.
11. Update documentation after each meaningful change.
12. Avoid regulated financial advice. Frame outputs as analysis, education,
    or decision-support.
13. Prefer mock data over risky integrations when demo reliability is at
    stake.
14. Keep the prototype simple, impressive, and demoable.

## Workflow commands

| Command | Output | Updates which doc |
|---|---|---|
| `/refine`  | Clarify WHAT we are building | `PROJECT_SPEC.md` (GIVEN/WHEN/THEN) |
| `/plan`    | Decide HOW to build it       | `DECISIONS.md` (architecture, trade-offs) |
| `/breakdown` | Split into vertical slices | `ROADMAP.md` (sequenced slices) |
| `/execute` | Build one independent slice  | Per-slice acceptance in `ACCEPTANCE_CRITERIA.md` |
| `/review`  | Independent review against spec & criteria | Verification log in `DECISIONS.md` |

## Pre-coding template (always output before /execute)

1. Slice name
2. What I will build
3. Files I will touch
4. Files I will not touch
5. Acceptance criteria
6. Test plan

## Post-coding template (always output after /execute)

1. What changed
2. How to test it
3. Evidence it works (screenshot, logs, exact test output)
4. Docs updated
5. Remaining risks

## Current artifact inventory (~/Plugin)

| Path | Purpose | Status |
|---|---|---|
| `fundsagent.py`   | Single-file FastAPI engine. Parser + matcher + planner + dossier. | Live, runnable, ~2200 lines |
| `Dockerfile`      | Cloud Run deploy target. | Live |
| `BRIEF.md`        | Cleaned hackathon brief (criteria, sponsors, format). | Live |
| `HACKATHON.md`    | Strategic note for the pitch. **Stale** — still references SWAN, predates the financing dossier pivot. | Needs refresh |
| `INSTALL.md`      | Cowork plugin install notice. | Live |
| `grant-matcher.plugin` | Cowork plugin (older deliverable). | Frozen |
| `CLAUDE.md`       | This file. | Live |
| `PROJECT_SPEC.md` | WHAT we're building (GIVEN/WHEN/THEN). | **Live** — produced by /refine on Apr 25 |
| `DECISIONS.md`    | Architecture + trade-offs + verification log. | **Live** — produced by /plan on Apr 25 |
| `ROADMAP.md`      | Sequenced vertical slices. | **Live** — produced by /breakdown on Apr 25 (13 slices) |
| `ACCEPTANCE_CRITERIA.md` | Per-slice acceptance criteria. | **Live** — produced by /breakdown on Apr 25 |
| `DEPLOYMENT.md`   | Step-by-step Google Cloud deploy guide (10 phases). | **Live** — produced Apr 25 |

## Stack snapshot

- **Engine** (current): Python 3.10+ · FastAPI · httpx · Cerebras OpenAI-compatible API.
- **Frontend** (production target): Lovable → consumes `/api/agent/run` (SSE) and `/dossier/<id>`.
- **Auth + DB** (production target): Firebase Auth + Firestore (sessions, dossier persistence).
- **Vector store** (if needed for grant-text RAG): Firestore Vector Search.
- **Deploy**: Cloud Run via AI Studio Build, single Docker image.
- **Models**: Cerebras `qwen-3-235b-a22b-instruct-2507` (default), Cerebras
  `llama3.1-8b` (cheaper); Gemini 3 Pro / Flash (multimodal fallback).

## Endpoints (current)

- `GET  /` — landing page (vanilla HTML SSE client)
- `POST /api/match` — synchronous match (no LLM streaming)
- `POST /api/agent/run` — SSE agent loop (parsed → matched → combos → plan → draft → dossier)
- `POST /api/upload` — PDF/PPTX text extraction
- `GET  /dossier/{id}` — printable A4 financing dossier (`?print=1` auto-prints)
- `GET  /api/dossier/{id}` — dossier as JSON
- `GET  /api/grants` — full grant catalogue (37 entries)
- `GET  /api/health` — readiness probe

## Hard constraints (judging-related)

| Score component | Weight | What we optimize for |
|---|---|---|
| Business Viability | 30% | Credible TAM/SAM, pricing model, financing dossier (VC language). |
| Technical Execution | 25% | Working demo, GitHub repo with commits in window, evidence-based. |
| Innovation & Originality | 20% | Use-of-funds inferred from sector + TRL, agent that asks for missing data, combinability matrix. |
| AI Integration | 15% | Cerebras parsing + planning + drafting; Gemini multimodal fallback; Grounding for live conditions. |
| Pitch & Presentation | 10% | 90-second demo flow with visible agent reasoning. |

## Demo invariants (do not break)

- **Sub-3-second loop** parse → match → plan → draft (Cerebras live).
- **Visible agent reasoning** via SSE stream (no silent LLM calls).
- **Two-click PDF export** (`Open dossier` → `Download PDF`).
- **Heuristic fallback** when `CEREBRAS_API_KEY` is absent — demo never blocks.
- **No regulated advice** — every score and recommendation framed as
  decision-support or analysis. The dossier carries a disclaimer block.

## Risks tracked

- **Cerebras rate limit** — observed 429 once during testing. Mitigation:
  short prompts (<8k chars), graceful fallback to heuristic.
- **SEDIA API instability** — best-effort, never blocking. Plugin already
  handles failure mode; bring this into `fundsagent.py` only when needed.
- **Indicative deadlines** — `DEADLINES_2026` is best-known, not live.
  Dossier disclaims this; plug live SEDIA before submission.
- **Stack pivot mid-hackathon** — Python single-file is engine, Lovable is
  production UI. The bridge is the JSON contract on `/api/agent/run`. Keep
  it stable.

## File-touch rules (enforced per slice)

- Slice may touch: `fundsagent.py` (engine), `frontend/*` (Lovable export, when present), the slice's own test file, the four spec docs.
- Slice may NOT touch: `BRIEF.md`, `HACKATHON.md`, `grant-matcher.plugin`,
  `CLAUDE.md` (unless the slice explicitly amends operating principles).

## Definition of done (per slice)

- [ ] Acceptance criteria from `ACCEPTANCE_CRITERIA.md` all green.
- [ ] Tests written before code (TDD strict).
- [ ] Lint + typecheck + tests pass.
- [ ] End-to-end manual verification with screenshot or log.
- [ ] Docs updated (`ROADMAP.md` slice marked done, `DECISIONS.md`
      verification log appended).
- [ ] No unrelated file modified.
