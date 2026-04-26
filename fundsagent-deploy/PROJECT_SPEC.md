# PROJECT_SPEC.md — FundsAgent

> Output of `/refine`. Source of truth for WHAT we are building.
> Read before `/plan`, `/breakdown`, `/execute`. Update only via `/refine`.

## 1. One-sentence product promise

**FundsAgent shows founders, in 30 seconds, which European public grants their startup is eligible for — and produces a VC-grade financing dossier they can share or print as a PDF.**

## 2. 60-second pitch (locked)

> *« Votre startup a droit à des dizaines de milliers d'euros de financement public. Personne ne vous l'a dit. FundsAgent le fait en 30 secondes. »*
>
> *« Construit en 24h sur Cerebras, Google Cloud et Lovable. Je vous le montre. »*

Three beats: existence (you have a right), diagnostic (the system failed to inform you), solution (testable promise of 30s, provable on stage).

## 3. Target persona

### Primary persona — The Solo / Early-Stage Founder

- **Profile** — CEO/CTO of a 1-15 person startup, deeptech or tech-driven, registered in an EU country (FR-anchored for the demo). Pre-seed to series A. May or may not have raised equity yet.
- **Context** — actively seeking funding, time-constrained, technical or scientific background but limited grant-writing experience.
- **Constraints** — cannot afford the €20-40k upfront fees of grant cabinets (Erdyn, Inno-tsd, F-Iniciativas, etc.). Has 30 minutes to evaluate this tool.
- **Awareness gap** — *does not know which programmes their startup is eligible for, and often does not know that programmes adapted to them exist at all.* This is the core pain.

### Customer (B2B2C, future scope)

- **Buyer** — incubator director or accelerator program manager (Station F, French Tech Tremplin, Numa, university incubators). Holds a portfolio of 20-200 startups in cohort.
- **Why they pay** — to deploy FundsAgent to their cohort founders as a service, and (in roadmap) to monitor portfolio funding pipeline at the aggregate level.
- **Pricing model (pitch slide only)** — €X / active founder / month, billed to the incubator. ~280 active incubators in France, ~12k deeptech startups in cohort annually.
- **In demo scope** — slide 7 of pitch deck only. **Not** built into the product surface for the hackathon.

### Out-of-scope persona — Grant consultants

Independent grant cabinets are *the gatekeepers FundsAgent disintermediates.* They are not a target customer; they are part of the problem statement. Do not design for them.

## 4. Core user journey (the demo flow, ~90 seconds)

```
[0:00] Founder lands on FundsAgent home page.
       Sees a single textarea + an upload button + 3 example pitchdeck buttons.

[0:05] Founder pastes pitchdeck text (or clicks "Example: GreenSilicon climate").

[0:08] Founder clicks ▶ Run agent.

[0:08-0:38] Agent streams its reasoning live as Server-Sent Events:
       • Parsing pitchdeck with Cerebras...                       (~0.5s)
       • Pitchdeck parsed: GreenSilicon · FR · TRL 5...           (visible)
       • Matching against 37 grants...                            (instant)
       • Found 17 eligible programmes, 6 in top tier              (visible)
       • Evaluating compatible combinations...                    (instant)
       • 5 strategic combinations identified                      (visible)
       • Building VC-grade financing plan with use-of-funds...    (~0.8s)
       • Plan ready: 4.5M€ ask, 4.28M€ grants expected            (visible)
       • Drafting Excellence section for top match...             (~0.7s)
       • Draft generated for Bpifrance ADI                        (visible)
       • Dossier ready                                            (link)

[0:38-1:05] Founder explores the result:
       • Top deadlines rail at the top (urgent first)
       • 6 grant cards (probability, fit, deadline pill, range)
       • Use-of-funds donut + funding sources stacked bar
       • Per-grant allocation breakdown
       • Excellence draft preview
       • Two CTAs: 📋 Copy link · 📄 Download PDF

[1:05] WHAT-IF moment (the agentic re-run):
       Founder bumps TRL 5 → 6 via inline input.
       Agent re-runs in ~1.5s.
       ERC PoC drops out (max TRL 5).
       EU Innovation Fund moves closer (min TRL 7 still blocks but visible).
       ADEME Démonstrateurs unlocks (min TRL 6).
       Probability stack reshuffles in real time.

[1:20] Founder clicks 📄 Download PDF.
       A4 dossier renders in print preview, exports to PDF.

[1:30] Pitch transitions to GTM / business viability slide.
```

The journey has **two visible climaxes**: the streaming agent loop (0:08-0:38) and the what-if re-match (1:05-1:20). Both are testable live.

## 5. User stories

Format: *As a [persona], I want [capability], so that [outcome].*

1. As a founder, I want to paste my pitchdeck and immediately know which public grants I am eligible for, so that I stop missing opportunities I did not know existed.

2. As a founder with an incomplete pitchdeck, I want the agent to tell me which critical fields are missing (TRL, country, funding amount), so that I provide them once and get a precise ranking instead of a degraded one.

3. As a founder considering my roadmap, I want to test *what if I were at TRL 6 next year?* without rewriting my pitchdeck, so that I can see which grants my next milestone unlocks.

4. As a founder, I want to download a VC-grade PDF dossier of my funding plan, so that I can share it with co-founders, advisors and investors as a professional document they recognize.

5. As a founder, I want to copy a shareable link to my dossier, so that my incubation manager or co-founder can review it from another device without me emailing a file.

6. As a founder ineligible to all matched grants, I want to see exactly what is blocking me, so that I can plan my next move (raise TRL, register an entity, change consortium openness).

7. As a founder, I want to see the upcoming deadlines for each eligible grant ranked by urgency, so that I prioritize what to apply to first.

8. As a founder in a sensitive sector (defence, gambling, crypto trading), I want to be warned about programme exclusions, so that I do not waste time on grants that will reject me by policy.

9. As a founder reading any score or recommendation, I want clear language that frames the tool as decision-support rather than financial advice, so that I do not over-rely on automated guidance for irreversible decisions.

## 6. Out of scope (the 24-hour discipline list)

The following are explicitly **not built** for the hackathon demo. Some appear in the pitch deck as future-work; none are coded.

### Product surfaces not built

- Incubator console (multi-tenant portfolio dashboard) — slide-only.
- Mobile-optimized UI — desktop demo only.
- Recurring user mode — no return sessions, no notifications, no email digests.
- Multi-pitchdeck batch processing — one pitchdeck at a time.
- Multiple comparison view (compare scenario A vs B side-by-side) — only one what-if variable, in place.

### Authentication & persistence

- No user accounts.
- No login.
- Dossiers persist in-memory only (lost on server restart). Dossier URLs are unguessable tokens, valid as long as the process runs.
- No user history, no saved drafts.

### Integrations not built

- No SWAN / banking integration (already dropped — not the right product fit per discussion).
- No live SEDIA refresh during the demo. `DEADLINES_2026` is a static map with a clearly labelled disclaimer. The plugin already has the live SEDIA client; bringing it into `fundsagent.py` is a future slice, not in the demo.
- No direct Bpifrance / ADEME / regional API integrations (their portals do not have public APIs).
- No calendar integration, no CRM integration.

### Workflow not built

- No application form auto-submit. We draft one section (Excellence) for the top match. The founder still writes the full dossier.
- No KYC / compliance audit trail / consortium agreement templates.
- No payment / subscription / billing flows.
- No multi-language UI (English-French content only; the engine accepts pitchdecks in either).

### Quality not built

- No calibration on private cohort. Scores are public-data heuristics. Limitation is disclosed in dossier.
- No A/B testing infrastructure.
- No analytics / telemetry.
- No accessibility audit (WCAG, screen-reader testing).

## 7. Acceptance criteria — GIVEN / WHEN / THEN

These are the binary tests that gate "done" for the demo build.
The corresponding test plans live in `ACCEPTANCE_CRITERIA.md` (per-slice).

### AC-01 — Happy path: pitchdeck → dossier in under 30 seconds

```
GIVEN  the application is running with a valid CEREBRAS_API_KEY
  AND  the user is on the home page
  AND  the user has pasted a complete pitchdeck text in English or French
       (containing at minimum: company name, country, sectors, TRL, funding amount)
WHEN   the user clicks "Run agent"
THEN   within 30 seconds (wall clock, measured from click),
       the agent has streamed at minimum these events: parsed, matched, combos, plan, draft, dossier
  AND  a dossier link is present and clickable
  AND  the link opens a printable A4 page containing all required sections.
```

### AC-02 — Missing-fields ask: agent halts and asks

```
GIVEN  a pitchdeck text that omits at least one critical field
       (TRL, country, or funding amount)
WHEN   the user clicks "Run agent"
THEN   the agent emits an `ask` event with the list of missing fields and a one-line rationale per field
  AND  no `matched` event is emitted yet
  AND  the UI presents one input per missing field with a "Re-run with answers" button
  AND  on submit, the agent resumes from `parsed` with the user's clarifications merged in.
```

### AC-03 — What-if iteration: change TRL, re-match in under 2 seconds

```
GIVEN  a completed first run with results displayed
  AND  a what-if input visible for TRL
WHEN   the user changes the TRL value (e.g. from 5 to 6)
  AND  triggers re-match (debounce or button)
THEN   the agent re-runs in under 2 seconds (wall clock)
  AND  the eligible grants list updates: at least one grant that was eligible at TRL 5 is now ineligible (or vice versa)
  AND  the dossier link is regenerated with the new state.
```

### AC-04 — Empty state: zero eligible grants

```
GIVEN  a pitchdeck whose profile makes all 37 grants ineligible
       (e.g. TRL 9 + non-EU country)
WHEN   the agent completes matching
THEN   the UI displays a no-match panel
  AND  the panel lists the three most common blockers across the 37 grants
       (e.g. "TRL too high for 12 programmes, country not eligible for 25, sector mismatch for 8")
  AND  the panel proposes at least one corrective action per blocker
       (e.g. "registering an EU entity unlocks 25 programmes")
  AND  no fictional or stretch grant is shown as eligible.
```

### AC-05 — Share link: copy dossier URL

```
GIVEN  a generated dossier visible in the browser
WHEN   the user clicks "Copy link"
THEN   the dossier URL (with its unguessable token) is written to the clipboard
  AND  a transient confirmation is shown ("Link copied")
  AND  pasting the URL in a fresh browser session opens the dossier without authentication
       (as long as the server has not restarted).
```

### AC-06 — PDF export: print to A4

```
GIVEN  the dossier page is open
WHEN   the user clicks "Download PDF"
THEN   the browser print dialog opens
  AND  on save-as-PDF, the resulting file fits A4 page sizing
  AND  the printed document includes, in order: header (company + sectors + TRL + ask),
       executive summary, KPI cards, use-of-funds donut, funding sources bar,
       top eligible grants table, submission timeline, allocation per grant,
       Excellence draft (if generated), disclaimers footer.
  AND  no UI chrome (buttons, sticky bar) appears in the printed output.
```

### AC-07 — Cerebras fallback: never block

```
GIVEN  CEREBRAS_API_KEY is unset OR Cerebras returns 429/5xx
WHEN   the user clicks "Run agent"
THEN   the agent falls back to the heuristic parser for `parsed`
  AND  the financing plan uses the sector-template defaults instead of the LLM-refined breakdown
  AND  the draft event payload contains a clear "[Cerebras unavailable — placeholder]" body
       rather than a fabricated paragraph
  AND  every other step (matched, combos, plan, dossier) still completes
  AND  total wall-clock time stays under 5 seconds.
```

### AC-08 — Sensitive-sector warning

```
GIVEN  a pitchdeck declaring sectors in the sensitive list
       (defence, gambling, weapons, crypto trading, adult content)
WHEN   matching runs
THEN   a banner is shown above the matches: "Sensitive sector detected — most public programmes apply specific exclusions; verify each call's policy before applying."
  AND  no grant is silently filtered out on this basis
       (we surface, we do not hide).
```

### AC-09 — Decision-support framing (regulatory hygiene)

```
GIVEN  any rendering of probability, score, or recommendation
WHEN   the user views the dashboard or the dossier
THEN   the language reads as analysis or decision-support
       (e.g. "blended probability", "fit composite", "indicative deadlines")
  AND  the dossier footer carries a four-line disclaimer covering:
       (1) probabilities are public-rate heuristics, not calibrated;
       (2) use-of-funds are sector-template defaults, refine with CFO;
       (3) cumulability rules apply, validate with granting authority;
       (4) this is a discussion document, not a regulatory filing.
```

### AC-10 — Demo invariants (the non-negotiables)

```
GIVEN  the standard demo flow with the GreenSilicon example pitchdeck
WHEN   we run it end-to-end against a Cloud Run deployment
THEN   the parse → match → plan → draft loop completes in under 3 seconds
  AND  every agent step emits a visible SSE event before the next starts
  AND  the dossier URL is reachable from the public deployment
  AND  the A4 PDF export works in Chrome and Safari without manual CSS hacks.
```

## 8. Locked decisions log (one-line summary of /refine answers)

| # | Decision | Locked value |
|---|---|---|
| Q1 | Target user | Founder-first; B2B2C with incubators as buyers (slide-only). |
| Q2 | Pain | Founder does not know what they are eligible for. |
| Q3 | Behaviour | One-shot complete + ONE what-if variable + share link. No auth, no recurrence. |
| Q4 | Output | A4 printable PDF dossier as the primary artifact. |
| Q5 | Empty state | Honest no-match with blockers + corrective actions. |
| Q6 | Out of scope | Incubator console punted to roadmap. |
| Q7 | 60s message | "Votre startup a droit à des dizaines de milliers d'euros... Personne ne vous l'a dit. FundsAgent le fait en 30s." |

## 9. Definition of "spec change"

This document changes only via a fresh `/refine`. Any /execute slice that touches behaviour assumed by an AC must update the AC in the same change.
