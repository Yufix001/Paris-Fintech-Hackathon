# ROADMAP.md — sequenced vertical slices

> Output of `/breakdown`. Order = demo risk reduction first, killer differentiation second, polish last.
> Each slice is independently buildable, testable, demoable. Sized 30-90 minutes.
> Per-slice `GIVEN/WHEN/THEN` + manual test + demo proof live in `ACCEPTANCE_CRITERIA.md`.

## Parallelization

Two dev tracks + designer track. Slices that touch the same file in `fundsagent.py` MUST be serialized on the same dev. The Lovable frontend is a separate codebase, designers own it.

```
Track A (Dev 1): S1 → S2 → S3 → S5 → S8 → S9
Track B (Dev 2): S2 (paired) → S4 → S6 → S7 → S11 → S12
Track C (designers): S10 (Lovable) → S13 (pitch deck)
```

S2 (Firestore) is paired — both devs sync on the schema before parallel work resumes.

## Dependency map

```
S1 deploy ─┐
            ├─→ S2 Firestore ─┬─→ S3 SEDIA ─┐
                              │              ├─→ S5 What-if ─┐
                              ├─→ S4 FR CSV ─┘                ├─→ S8 Deep-dive
                              │                                ├─→ S9 Citations
                              └─→ S6 Copy ─→ S7 PPTX ─────────┘

S10 Lovable consumes the API — runs in parallel once S2 is up
S11 Tests + CI    — picks up after S7
S12 Smoke + runbook — picks up after S9
S13 Pitch deck    — runs in parallel from H+0
```

## The 13 slices

### Slice 1 — Public Cloud Run deployment 🟡 deploy-ready

> **Status**: deploy artifacts shipped, awaiting `bash scripts/deploy.sh` from a
> machine with `gcloud` authenticated to your GCP project. Local equivalent of
> all ACs validated (server boots, `/api/health` returns the expected shape,
> end-to-end agent run with Cerebras live = 2.11 s on local).

**1. name**: S1 — Cloud Run deploy of current `fundsagent.py`
**2. user-visible outcome**: a public HTTPS URL (`https://fundsagent-<hash>.europe-west1.run.app`) where any browser can paste a pitchdeck and get a dossier — *the demo URL is real, not localhost*.
**3. scope**: build the existing image via `gcloud run deploy --source .`, set env vars (`CEREBRAS_API_KEY`, `GEMINI_API_KEY` for next slices), `--min-instances=1` for the pitch window, `--allow-unauthenticated`, smoke-test the deployed URL with the GreenSilicon example.
**4. out of scope**: custom domain, CDN, IAM, multi-region, pricing optimization.
**5. files likely touched**: `Dockerfile` (already exists), `.gcloudignore` (new — exclude `tests/`, `*.md`, `__pycache__`, `*.plugin`), `README.md` (add Run/Deploy section + the live URL badge).
**6. acceptance criteria**: AC-S1 in `ACCEPTANCE_CRITERIA.md`.
**7. manual test**: `curl https://<url>/api/health` returns 200 with `cerebras_configured: true`. Open `/`, click GreenSilicon example, click Run, watch SSE stream complete, click dossier link, click Download PDF — full flow on the live URL.
**8. demo proof**: screenshot of the deployed `/api/health` JSON + a successful agent run on the public URL.

---

### Slice 2 — Firestore-backed dossier persistence (paired)

**1. name**: S2 — Firestore replaces in-memory `DOSSIER_STORE`
**2. user-visible outcome**: a dossier link generated at H-0 still works after a redeploy at H+1. Share link survives Cloud Run restart.
**3. scope**: add `google-cloud-firestore` to `Dockerfile`, create Firebase project + service account JSON, replace `DOSSIER_STORE = {}` and `_store_dossier` with Firestore reads/writes (collection `dossiers`, doc id = unguessable token), keep an LRU memory cache (32 entries) for hot reads. Define the Firestore schema for `grants_eu`, `grants_fr`, `dossiers` collections — devs sync here so S3/S4 can write to known shapes.
**4. out of scope**: full data migration (we don't carry old dossiers), multi-region replication, Firestore Vector Search (S8 territory), TTL.
**5. files likely touched**: `fundsagent.py` (lines 791-811 `DOSSIER_STORE` + `_store_dossier`, also `dossier()` route at 1519-1524), `requirements.txt` or `Dockerfile` for the dep, `firebase-credentials.json` mount (Cloud Run env var `GOOGLE_APPLICATION_CREDENTIALS`).
**6. acceptance criteria**: AC-S2.
**7. manual test**: generate a dossier, copy URL, restart `fundsagent.py` (locally `kill + python fundsagent.py`, on Cloud Run `gcloud run deploy` again), open the URL → dossier loads.
**8. demo proof**: log line `[firestore] wrote dossier <id>` + screenshot of the Firestore console showing the document.

---

### Slice 3 — Live SEDIA refresh for EU deadlines

**1. name**: S3 — SEDIA Search API integration in hot path
**2. user-visible outcome**: each of the 22 EU grants displays its **real** next deadline (refreshed from SEDIA daily) with a green "Live · refreshed 2h ago" badge — instead of the current static `DEADLINES_2026` map. The dossier footer reads "Source: SEDIA refreshed 2026-04-25 06:00 UTC".
**3. scope**: write `scripts/refresh_sedia.py` (a Cloud Run Job entrypoint) that hits `https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA` per EU programme prefix (HORIZON-CL5-, EIC-, LIFE-, etc.), parses status + deadlineDate, writes to Firestore `grants_eu/{grant_id}` with `next_deadline`, `data_freshness`, `source: "sedia"`. Cloud Scheduler triggers nightly at 04:00 UTC. `fundsagent.py` reads Firestore at startup (and per-request with 5min cache).
**4. out of scope**: CORDIS success-rate derivation (a follow-up), full call eligibility text (auth-protected), French programmes (S4), per-call attachment retrieval.
**5. files likely touched**: `scripts/refresh_sedia.py` (new, ~120 lines reusing the plugin's `sedia.py` client), `fundsagent.py` (replace static `DEADLINES_2026` lookup with `firestore_lookup()`, ~30-line refactor), `cloudbuild-job.yaml` (new — Cloud Run Job manifest), `cloudscheduler.yaml` (new — cron trigger).
**6. acceptance criteria**: AC-S3.
**7. manual test**: run `python scripts/refresh_sedia.py` locally with creds, check Firestore `grants_eu` collection has 22 docs each with `next_deadline` + `data_freshness` < 1 minute ago. Reload the dashboard — EU grants show "Live · refreshed N seconds ago".
**8. demo proof**: Firestore console screenshot + agent run with at least one EU grant pill showing a deadline that matches the actual SEDIA portal.

---

### Slice 4 — French CSV ingestion + Gemini structured extraction

**1. name**: S4 — `aides-entreprises.fr` → Firestore via Gemini
**2. user-visible outcome**: the 15 French/regional grants display structured eligibility (TRL range, sectors, SME requirement, funding range) extracted from the official `data.aides-entreprises.fr/files/aides.csv` via Gemini 3 Pro. Each card shows "Source: aides-entreprises.fr · last verified 2026-04-25" with a clickable link to the official application form.
**3. scope**: write `scripts/refresh_fr.py` that downloads the CSV (5.8 MB, latin-1), filters to our 15 programme names + financeur ids, calls Gemini 3 Pro with structured-output JSON mode + our `GrantEntry` schema for each entry, writes Firestore `grants_fr/{grant_id}`. Same Cloud Scheduler nightly. Add validation: reject if Gemini returns missing required fields.
**4. out of scope**: aides-territoires API integration (S4-bis later), regional API portals, real-time webhook on CSV updates, automated diff alerting.
**5. files likely touched**: `scripts/refresh_fr.py` (new, ~150 lines), `fundsagent.py` (read FR grants from Firestore at startup), `tests/test_extraction.py` (new — fixture: 5 CSV rows → expected JSON).
**6. acceptance criteria**: AC-S4.
**7. manual test**: run `python scripts/refresh_fr.py` locally. Open Firestore console: 15 docs in `grants_fr`, each with `aid_name`, `source_url` ending in `aides-entreprises.fr/aide/<id>`, `extraction_method: "gemini-3-pro"`, `last_verified_at` < 1 min. Reload dashboard, click on Bpifrance ADI card → see the source link.
**8. demo proof**: side-by-side screenshot — Firestore doc + the actual `aides-entreprises.fr` page, showing the source URL matches.

---

### Slice 5 — What-if TRL re-match (the agentic moment)

**1. name**: S5 — TRL slider triggers re-run in <2s
**2. user-visible outcome**: in the results panel, an inline TRL input (5 → 6) is visible. Founder changes it; agent re-runs in <2s; eligible grants list updates with **visible additions and removals** (ERC PoC drops out, ADEME unlocks, etc.).
**3. scope**: add `<TRLAdjuster>` UI block under the matched-grants section. Hooks `POST /api/agent/run` with `pitchdeck_json` set to the previously-parsed JSON + `trl` overridden + `skip_parse: true` flag. Engine skips step 1 (parse) and runs steps 4-8 from the existing flow. Visual diff: grants list flashes green for added, red strikethrough for removed (animation 0.5s).
**4. out of scope**: multiple what-if axes (only TRL for now), persistent comparison view, history of past attempts.
**5. files likely touched**: `fundsagent.py` HTML inline (lines 2009-2070, add TRL adjuster + diff animation), `fundsagent.py` `GrantAgent.run` (`skip_parse` flag, ~10 lines added at line 1320), Lovable mirror `<WhatIfPanel>`.
**6. acceptance criteria**: AC-S5.
**7. manual test**: paste GreenSilicon (TRL 5), run agent. After matched event, see TRL adjuster. Change to 6, click Re-match. Within 2 seconds, ERC PoC grant card has strikethrough (max TRL 5), ADEME Démonstrateurs is highlighted as newly eligible.
**8. demo proof**: screen recording of the TRL change with grants visibly reshuffling. This is THE demo moment.

---

### Slice 6 — Copy share link

**1. name**: S6 — Clipboard share URL with confirmation toast
**2. user-visible outcome**: a `📋 Copy link` button next to `📄 Download PDF` on the dossier CTA. Click → URL in clipboard, transient toast "Link copied". Pasting in a fresh browser session opens the same dossier.
**3. scope**: add the button to the dossier CTA block in HTML inline + Lovable. JS: `navigator.clipboard.writeText(url)` + 2s toast. Backend: nothing changes (dossier URL works since S2).
**4. out of scope**: short URL service, expiring tokens, ACL on shared links, "share via email" prefilled mailto.
**5. files likely touched**: `fundsagent.py` HTML/JS (the `renderDossier` JS function), Lovable `<DossierActions>` component.
**6. acceptance criteria**: AC-S6.
**7. manual test**: generate dossier, click `📋 Copy link`, see "Link copied" toast for 2s. Open incognito, paste, dossier loads with same content.
**8. demo proof**: 5-second screen recording of click → toast → paste-in-incognito → dossier opens.

---

### Slice 7 — Image-only PPTX multimodal fallback

**1. name**: S7 — Gemini 3 Flash extracts text from image-heavy PPTX
**2. user-visible outcome**: a juror who uploads a PPTX where every slide is an image (no copyable text) gets the same flow as text. Agent stream shows "PPTX text extraction returned <100 chars → using Gemini multimodal vision..." then proceeds normally.
**3. scope**: detect in `extract_text_from_pptx` that text length is <100 chars → render each slide to PNG (via `python-pptx` + Pillow) → send to Gemini 3 Flash multimodal with prompt "extract all text from this slide" → concatenate. Add `gemini_multimodal_fallback` flag in the response.
**4. out of scope**: OCR of native PDFs (their text layer usually works), handwriting recognition, slide-by-slide structured layout (just plain text).
**5. files likely touched**: `fundsagent.py` `extract_text_from_pptx` (lines 1262-1289, add fallback branch), new `extract_pptx_via_vision` helper (~60 lines), `Dockerfile` (add Pillow), `tests/fixtures/image_only_deck.pptx` (new test fixture).
**6. acceptance criteria**: AC-S7.
**7. manual test**: upload `tests/fixtures/image_only_deck.pptx` (a real PPTX where text is rasterized inside images). Watch agent stream emit the multimodal fallback message. Verify the parsed JSON contains the company info that was visible only in image form.
**8. demo proof**: screenshot of agent stream with the "using Gemini multimodal" line + parsed JSON containing the right company name.

---

### Slice 8 — Deep-dive Agent E (compliance checklist on EIC Accelerator)

**1. name**: S8 — On-demand criterion-by-criterion compliance check
**2. user-visible outcome**: founder clicks a `🔬 Deep dive` button on the EIC Accelerator card. New panel opens. Agent streams "Loading 23 criteria from EIC Accelerator 2026 call doc..." → "Checking criterion 1/23: 'breakthrough innovation potential'..." with a checkmark or cross per criterion. After ~10-15 seconds, returns: "18/23 criteria validated. 5 gaps identified" with each gap listed with corrective action.
**3. scope**: manually curate `data/eic_accelerator_criteria.json` (23 criteria, each with `id`, `title`, `description`, `weight`, `source_section`). Build `POST /api/agent/deep-dive` endpoint that streams SSE: takes `pitchdeck_json` + `grant_id`, retrieves criteria from Firestore, calls Gemini 3 Pro with structured JSON output `{criterion_id, status: pass|partial|fail, evidence_in_pitchdeck, gap_explanation}` for each criterion (in batches of 5 to avoid context overflow), aggregates, returns the checklist. UI panel shows the checklist with green/orange/red rows.
**4. out of scope**: clickable citations to the actual call PDF (S9), deep-dive on the other 21 EU grants (S8 = EIC Accelerator only for the demo), founder uploading additional supporting docs to refine the check.
**5. files likely touched**: `fundsagent.py` (new endpoint ~80 lines, new event types `deep_dive_*` in `AgentEvent`), `data/eic_accelerator_criteria.json` (new, manually curated from the public 2026 work programme), HTML/Lovable `<DeepDivePanel>`, `tests/test_deep_dive.py`.
**6. acceptance criteria**: AC-S8.
**7. manual test**: paste GreenSilicon, run agent, click 🔬 on EIC Accelerator card. Within 15s, see the checklist with at least 15 green rows, at least 3 amber/red rows, each row with explanation tied to the pitchdeck content.
**8. demo proof**: screen recording of the deep-dive flow start to finish (~15s). This is the multi-agent killer moment for the pitch.

---

### Slice 9 — Deep-dive citations (the unfair advantage)

**1. name**: S9 — Each criterion has a clickable citation pointing to the call paragraph
**2. user-visible outcome**: in the deep-dive checklist (S8), each row has `📑 view source`. Click → modal opens showing the exact paragraph from the EIC Accelerator 2026 work programme PDF, with the relevant criterion highlighted. Founder can verify the AI's claim against the official source.
**3. scope**: ingest the EIC Accelerator 2026 work programme PDF (publicly downloadable from CINEA) once via Document AI Layout Parser → produce sections with paragraph IDs + page numbers. Store sections + embeddings (text-embedding-004) in Firestore Vector Search. In Agent E (S8), per criterion, retrieve the top-3 paragraphs by cosine similarity to the criterion description; pass to Gemini for verification. Return citations `{paragraph_id, page_number, text_excerpt}` alongside the pass/fail status. Modal in UI shows the excerpt.
**4. out of scope**: ingestion of work programme PDFs for other 21 EU grants (S9-bis later), full PDF rendering in the modal (text excerpts are enough), verification of Gemini citations against the original PDF (we trust the retrieval).
**5. files likely touched**: `scripts/ingest_call_doc.py` (new, ~100 lines), `fundsagent.py` deep-dive endpoint (extend with retrieval), Lovable `<CitationModal>`.
**6. acceptance criteria**: AC-S9.
**7. manual test**: do a deep-dive, click 📑 on the "breakthrough innovation potential" criterion. Modal opens. Excerpt visible from page X of the EIC Accelerator work programme, with the keyword "breakthrough" highlighted. Compare to the actual PDF on CINEA — same paragraph.
**8. demo proof**: screen recording of click → modal → excerpt + the corresponding page of the official PDF for proof.

---

### Slice 10 — Lovable production frontend (designer track)

**1. name**: S10 — Polished UI mirror in Lovable consuming the Cloud Run API
**2. user-visible outcome**: a public Lovable URL (`<project>.lovable.app`) loads a polished landing page → consumes `POST /api/agent/run` SSE → renders the same agent flow with better typography, animations, mobile-responsive. Clicking dossier embeds `/dossier/<id>` in iframe. Falls back to the Python URL if Lovable is down.
**3. scope**: vibe-code in Lovable a Next.js app with `<PitchdeckInput>`, `<AgentStream>`, `<AskClarification>`, `<DeadlineRail>`, `<GrantCard>`, `<FundingPlan>` (renders server-provided SVG via `dangerouslySetInnerHTML`), `<WhatIfPanel>`, `<DeepDivePanel>`, `<DossierActions>`. CORS on Python backend allow Lovable's origin. Type generation from `/openapi.json` via `openapi-typescript`.
**4. out of scope**: server-side rendering, i18n, dark mode, custom domain, analytics, mobile-app wrapping.
**5. files likely touched**: Lovable project (new) — separate codebase. `fundsagent.py` adds CORS middleware (allow Lovable origin).
**6. acceptance criteria**: AC-S10.
**7. manual test**: open Lovable URL → run agent flow end-to-end → results match the Python URL. Test on iPhone Safari + Chrome desktop.
**8. demo proof**: side-by-side screenshots of Python URL vs Lovable URL on the same input — same data, polished UI.

---

### Slice 11 — Tests committed + GitHub Actions CI

**1. name**: S11 — `pytest + pyright + ruff` green badge in README
**2. user-visible outcome**: judges who open the GitHub repo see a green "tests passing" badge in the README. The repo has 8+ unit tests on the matcher and 4+ integration tests on the API. Every push runs them in CI.
**3. scope**: write `tests/test_matcher.py` (8 unit tests covering `check_eligibility`, `compute_fit`, `statistical_estimate`, `simulate_evaluator`, `blend_probability`, `evaluate_combinations`, `match_grant`, `_credible_funding_ask`), `tests/test_api.py` (4 integration tests with `httpx.AsyncClient(app=app)` and mocked `cerebras_chat` covering AC-01, AC-02, AC-04, AC-07), `tests/conftest.py` (fixtures), `pyproject.toml` (pyright strict + ruff config), `.github/workflows/ci.yml`. Update `README.md` with badge.
**4. out of scope**: end-to-end Playwright tests (overkill), code coverage thresholds, mutation testing, perf benchmarks.
**5. files likely touched**: all `tests/*` (new), `.github/workflows/ci.yml` (new), `pyproject.toml` (new), `README.md` (badge + Run Tests section).
**6. acceptance criteria**: AC-S11.
**7. manual test**: `pytest -v` locally → all green. Push to GitHub → Actions tab shows the run. README badge turns green.
**8. demo proof**: GitHub Actions run summary screenshot (12 tests passed, 0 failed) + the README badge.

---

### Slice 12 — Smoke deploy script + demo runbook

**1. name**: S12 — `scripts/smoke_demo.sh` + `docs/DEMO_CHECKLIST.md`
**2. user-visible outcome**: any team member can run one command 5 minutes before the pitch and know whether the deployed URL is healthy. The checklist guides the pre-pitch warmup.
**3. scope**: bash script that hits `/api/health`, posts the GreenSilicon example to `/api/agent/run`, asserts the dossier link is reachable in <30s, prints a green/red verdict. Companion 10-line markdown checklist (warmup ping, hotspot tethering, fallback URL bookmarked, recording cached, browser version pinned).
**4. out of scope**: load testing, chaos engineering, automated rollback, on-call rotation.
**5. files likely touched**: `scripts/smoke_demo.sh` (new, ~40 lines), `docs/DEMO_CHECKLIST.md` (new, ~30 lines).
**6. acceptance criteria**: AC-S12.
**7. manual test**: run `./scripts/smoke_demo.sh https://<deployed-url>` → exits 0 with summary "✓ Health · ✓ Agent run 2.1s · ✓ Dossier reachable". Tamper with `CEREBRAS_API_KEY` → script exits non-zero with the failure pinpointed.
**8. demo proof**: terminal capture of a green run + the checklist as committed markdown.

---

### Slice 13 — Pitch deck assembly (designer track)

**1. name**: S13 — 10-slide PDF that wraps the demo
**2. user-visible outcome**: a polished `pitch-deck.pdf` in the repo, max 10 slides, covering: the 60s message · problem stats · solution overview · 3 demo screenshots · architecture diagram · business model + GTM via incubateurs · 3 sponsor integrations · team · ask + what's next.
**3. scope**: slides built in Lovable's deck mode OR Google Slides → exported PDF. Sources for the problem stats committed in `docs/PITCH_SOURCES.md` (cabinets pricing, France Digitale 2024 access study, Bpifrance disbursement data). The 60s message verbatim from `PROJECT_SPEC.md §2`.
**4. out of scope**: video sizzle reel, animation flourishes, multiple language versions, narrated voiceover.
**5. files likely touched**: `pitch-deck.pdf` (new, committed binary), `docs/PITCH_SOURCES.md` (new), Lovable deck or Google Slides URL in README.
**6. acceptance criteria**: AC-S13.
**7. manual test**: open the PDF, count slides ≤10, verify the 60s message appears verbatim on slide 1, demo screenshots match the actual deployed UI, sources cited on the appropriate slide.
**8. demo proof**: PDF committed in the repo + the 60s message read out loud in 60 seconds with a stopwatch.

---

## Cumulative time budget

| Track | Slices | Sum estimated time | Real elapsed (parallel) |
|---|---|---|---|
| Track A (Dev 1) | S1, S2, S3, S5, S8, S9 | 60+45+90+75+120+90 = 480 min = **8 h** | 8 h |
| Track B (Dev 2) | S2, S4, S6, S7, S11, S12 | 45+90+30+60+90+30 = 345 min = **5 h 45** | 5 h 45 |
| Track C (designers) | S10, S13 | 90+90 = 180 min = **3 h** | 3 h (split between 3 designers) |

Real critical path = Track A at 8h. Slice 8 is the longest single slice (~2h) and the highest-value differentiation — it's worth the elasticity if it overruns.

Buffer of ~16 hours over 24h hackathon. That buffer absorbs:
- integration friction between slices
- the inevitable Cerebras/Vertex AI debug cycles
- pitch rehearsal (3-4 dry runs of the 90s pitch)
- last-mile sponsor name-checks and slide tweaks

## Definition of "slice done" (every slice)

- [ ] All 8 fields in the slice card are met (manual test passes, demo proof captured)
- [ ] Acceptance criteria green per `ACCEPTANCE_CRITERIA.md`
- [ ] Tests for this slice are committed and passing in CI (where applicable)
- [ ] No unrelated file touched (per `CLAUDE.md` file-touch rules)
- [ ] `ROADMAP.md` slice marked ✅ done with the commit SHA
- [ ] `DECISIONS.md` verification log appended with one-line summary
