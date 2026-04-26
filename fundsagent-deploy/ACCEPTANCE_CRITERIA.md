# ACCEPTANCE_CRITERIA.md — per-slice GIVEN/WHEN/THEN

> Output of `/breakdown` (companion to `ROADMAP.md`). Each slice in `ROADMAP.md`
> has its detailed AC + manual test + demo-proof here.
> The high-level product ACs (AC-01 to AC-10) live in `PROJECT_SPEC.md §7`
> — they are the **target** that the sum of slices satisfies.
>
> Convention: `AC-Sx` = acceptance criterion for slice `x`. Multiple sub-criteria
> as `AC-Sx.1`, `AC-Sx.2`, etc. when needed.

---

## AC-S1 — Cloud Run deploy

```
AC-S1.1   Public URL responds 200 on /api/health
GIVEN  the Cloud Run service is deployed in europe-west1
  AND  CEREBRAS_API_KEY is set as a secret env var
  AND  --min-instances=1 is configured
  AND  --allow-unauthenticated is set
WHEN   any user visits https://<service-url>/api/health
THEN   the response is 200 OK
  AND  the JSON body contains "status": "ok"
  AND  the JSON body contains "cerebras_configured": true
  AND  the JSON body contains "grants_loaded": 37
```

```
AC-S1.2   End-to-end flow on the live URL
GIVEN  the deployed URL is reachable
WHEN   a user pastes the GreenSilicon example pitchdeck
  AND  clicks Run agent
THEN   the agent stream completes within 5 seconds (cold-start tolerated)
  AND  a dossier link is displayed
  AND  the dossier link returns 200 and renders the A4 page
```

**Manual test**:
1. `gcloud run deploy fundsagent --source . --region=europe-west1 --min-instances=1 --set-env-vars CEREBRAS_API_KEY=$CEREBRAS_API_KEY --allow-unauthenticated`
2. Note the public URL.
3. `curl <url>/api/health` → check JSON shape.
4. Open `<url>` in a browser, click Example: GreenSilicon, click Run agent.
5. Wait, click dossier link, click Download PDF.

**Demo proof**: screenshot of the deployed `/api/health` JSON output + a screenshot of the dossier rendered from the live URL with timestamp visible.

---

## AC-S2 — Firestore persistence

```
AC-S2.1   Dossiers persist across server restarts
GIVEN  the service is running and a dossier exists with id <D>
WHEN   the service is restarted (process kill + restart, or new Cloud Run revision)
THEN   GET /dossier/<D> still returns the rendered HTML with the same content
  AND  GET /api/dossier/<D> returns the same JSON payload
```

```
AC-S2.2   Schema established for collaborating slices
GIVEN  Firestore project is provisioned
THEN   the following collections exist with documented shape:
  • dossiers/{token} : { deck, matches, combos, plan, draft, stats, generated_at }
  • grants_eu/{grant_id} : { ...grant, source: "sedia"|"manual", data_freshness, last_verified_at }
  • grants_fr/{grant_id} : { ...grant, source: "aides-entreprises"|"manual", extraction_method, last_verified_at }
  AND  the schema is committed in DECISIONS.md §5 (data models)
```

**Manual test**:
1. Run `python fundsagent.py` locally with `GOOGLE_APPLICATION_CREDENTIALS` set.
2. Generate a dossier via the UI → note id <D>.
3. `curl <local>/dossier/<D>` → 200 + content.
4. `Ctrl-C` then `python fundsagent.py` again.
5. `curl <local>/dossier/<D>` → still 200 with identical content.
6. Open the Firestore console → check `dossiers/<D>` exists with the stored payload.

**Demo proof**: terminal showing the kill+restart, the second `curl` succeeding, and a Firestore console screenshot of the document.

---

## AC-S3 — SEDIA live refresh

```
AC-S3.1   Refresh job populates Firestore for 22 EU grants
GIVEN  scripts/refresh_sedia.py is invoked with creds
WHEN   the script completes
THEN   Firestore collection grants_eu has exactly 22 documents
  AND  every document has a non-null next_deadline (ISO 8601) OR explicit "rolling": true
  AND  every document has data_freshness within the last 60 seconds
  AND  every document has source: "sedia"
```

```
AC-S3.2   Hot path reads from Firestore, displays freshness pill
GIVEN  Firestore grants_eu is populated
WHEN   the founder runs the agent and looks at any EU grant card
THEN   the deadline matches the Firestore value
  AND  the card shows a "Live · refreshed Nh ago" pill
  AND  the dossier footer reads "Source: SEDIA refreshed <ISO>"
```

```
AC-S3.3   Cloud Scheduler triggers nightly
GIVEN  the Cloud Scheduler job is configured for 04:00 UTC daily
WHEN   24 hours have passed since deploy
THEN   the Cloud Run Job has at least 1 successful invocation
  AND  Firestore data_freshness has advanced
```

**Manual test**:
1. `python scripts/refresh_sedia.py` locally.
2. Open Firestore console: 22 docs in `grants_eu`, freshness < 1 min.
3. Reload the dashboard, run the agent — EU cards display "Live · refreshed Xs ago".
4. Cross-check ONE deadline (e.g., EIC Accelerator) against the actual SEDIA portal URL → match.

**Demo proof**: Firestore console + dashboard screenshot showing the freshness pill + a side-by-side with a SEDIA portal page proving the deadline is live.

---

## AC-S4 — French CSV + Gemini extraction

```
AC-S4.1   CSV ingestion populates 15 FR grants
GIVEN  scripts/refresh_fr.py is invoked with GEMINI_API_KEY
WHEN   the script completes
THEN   Firestore collection grants_fr has exactly 15 documents (the curated list)
  AND  every document has aid_name, source_url, extraction_method, last_verified_at
  AND  every source_url returns 200 OK
  AND  every document conforms to the GrantEntry schema (validated)
```

```
AC-S4.2   Gemini extraction is structurally valid
GIVEN  a sample of 5 raw CSV rows representing France 2030 / Bpifrance / ADEME / FEDER / Innov'Up
WHEN   the extraction prompt runs against Gemini 3 Pro structured output
THEN   for each, the returned JSON has all required fields populated
  AND  trl_min, trl_max, sme_required match the human reading of aid_conditions
  AND  funding_range_eur values are within an order of magnitude of aid_montant text
  AND  if Gemini fails to populate any required field, the script raises and aborts
```

```
AC-S4.3   UI displays source URL on each FR card
GIVEN  Firestore grants_fr is populated
WHEN   the founder clicks a French grant card
THEN   a "Source: aides-entreprises.fr · last verified <date>" line appears
  AND  the line contains a clickable link to the official application form
```

**Manual test**:
1. `python scripts/refresh_fr.py` locally.
2. Firestore console: 15 docs in `grants_fr`, all with `source_url` populated.
3. Click 3 random source URLs → all open the official form.
4. Reload dashboard, click on Bpifrance ADI card → see the source link → click → opens `aides-entreprises.fr/aide/<id>`.

**Demo proof**: side-by-side screenshot — Firestore doc + the `aides-entreprises.fr` page, with the URL matching.

---

## AC-S5 — What-if TRL re-match

```
AC-S5.1   TRL adjuster appears after first run
GIVEN  the founder has completed an agent run
WHEN   the matched event has been processed by the UI
THEN   a TRL adjuster widget is visible above the matches list
  AND  the current TRL is pre-filled
```

```
AC-S5.2   Re-run completes in under 2 seconds
GIVEN  a completed first run
WHEN   the founder changes the TRL value and triggers re-match
THEN   the agent re-runs without re-parsing (skip_parse: true)
  AND  the new matched event arrives within 2 seconds (wall clock)
  AND  the eligible-grants list updates
  AND  the dossier link is regenerated with the new state
```

```
AC-S5.3   Visible diff: at least one grant added or removed
GIVEN  a TRL change from 5 to 6 (or vice versa) on the GreenSilicon example
WHEN   the re-match completes
THEN   at least one grant card appears or disappears compared to the previous state
  AND  added grants are visually highlighted (1s green flash)
  AND  removed grants are struck through (1s red flash before removal)
```

**Manual test**:
1. Paste GreenSilicon (TRL 5), run agent.
2. After matched event, TRL adjuster visible.
3. Change to 6, click Re-match.
4. Stopwatch: re-match completes < 2s.
5. ERC PoC card has strikethrough (TRL max 5).
6. ADEME Démonstrateurs card flashes green (TRL min 6).

**Demo proof**: 5-second screen recording of the TRL change with the diff animations.

---

## AC-S6 — Copy share link

```
AC-S6.1   Click copies the URL with a confirmation toast
GIVEN  a generated dossier with id <D>
WHEN   the founder clicks "📋 Copy link"
THEN   the clipboard contains "https://<host>/dossier/<D>"
  AND  a transient toast "Link copied" appears for ≥1.5 seconds
```

```
AC-S6.2   Pasted URL opens the dossier without auth
GIVEN  the URL is in the clipboard
WHEN   the user opens a fresh browser session (or incognito) and pastes the URL
THEN   the dossier loads with all sections intact (executive summary, plan, grants, draft, disclaimer)
  AND  no login or token prompt appears
```

**Manual test**:
1. Generate dossier, click Copy link, see toast.
2. Open Chrome incognito, paste in address bar, hit Enter.
3. Dossier loads.

**Demo proof**: 5-second screen recording of click → toast → paste-in-incognito → dossier renders.

---

## AC-S7 — PPTX multimodal fallback

```
AC-S7.1   Detection of low text content triggers fallback
GIVEN  a PPTX file is uploaded via /api/upload
  AND  python-pptx text extraction returns <100 characters
WHEN   /api/upload processes the file
THEN   it falls back to gemini_multimodal_fallback
  AND  the response includes "extraction_method": "gemini-multimodal"
```

```
AC-S7.2   Vision extraction returns usable text
GIVEN  a fixture image-only PPTX with a known company name "Visionary Labs"
WHEN   the Gemini multimodal fallback runs
THEN   the returned text contains "Visionary Labs"
  AND  the parsed pitchdeck JSON has company.name = "Visionary Labs"
```

```
AC-S7.3   Agent stream surfaces the fallback to the user
GIVEN  the multimodal fallback is invoked during an agent run
WHEN   the user watches the SSE stream
THEN   one of the thinking events contains "multimodal" or "vision"
  AND  the stream completes without error
```

**Manual test**:
1. Use the bundled `tests/fixtures/image_only_deck.pptx`.
2. Upload via the UI.
3. Watch agent stream emit "PPTX text low → using Gemini multimodal vision...".
4. Verify the parsed JSON contains the right company info.

**Demo proof**: screenshot of the agent stream with the fallback message + parsed JSON.

---

## AC-S8 — Deep-dive Agent E (compliance checklist)

```
AC-S8.1   Deep-dive button is present on the EIC Accelerator card
GIVEN  the founder has run the agent on a profile that matches EIC Accelerator
WHEN   the matched event is rendered
THEN   the EIC Accelerator card shows a "🔬 Deep dive" button
```

```
AC-S8.2   Deep-dive endpoint streams the criterion-by-criterion check
GIVEN  the founder clicks Deep dive
WHEN   POST /api/agent/deep-dive is invoked with pitchdeck_json + grant_id="eic_accelerator"
THEN   the SSE stream emits at least 23 deep_dive_criterion events
  AND  each event payload has criterion_id, status (pass|partial|fail), evidence_in_pitchdeck, gap_explanation
  AND  the stream emits a final deep_dive_summary event with counts: pass, partial, fail
  AND  total wall-clock time is under 20 seconds
```

```
AC-S8.3   UI renders the checklist with pass/partial/fail visual cues
GIVEN  the deep-dive stream has completed
WHEN   the user looks at the deep-dive panel
THEN   23 rows are visible
  AND  green rows have a checkmark, amber rows a warning, red rows a cross
  AND  each row shows the gap_explanation below the title
```

**Manual test**:
1. Paste GreenSilicon, run agent.
2. Click 🔬 Deep dive on EIC Accelerator card.
3. Within 15s, see the checklist.
4. Spot-check 3 rows against the GreenSilicon pitchdeck content — explanations are anchored on real pitchdeck facts.

**Demo proof**: screen recording of the click → 15s stream → final checklist with at least 18 green rows out of 23.

---

## AC-S9 — Deep-dive citations

```
AC-S9.1   Work programme PDF is ingested into the vector store
GIVEN  the EIC Accelerator 2026 work programme PDF is downloaded
WHEN   scripts/ingest_call_doc.py runs
THEN   Document AI Layout Parser produces ≥40 sections (paragraph_id, page, text)
  AND  each section is embedded via text-embedding-004
  AND  Firestore Vector Search index "eic_accelerator_call_2026" has ≥40 entries
```

```
AC-S9.2   Each criterion in deep-dive returns top-3 citations
GIVEN  the deep-dive endpoint runs with citations enabled
WHEN   per-criterion retrieval executes
THEN   each criterion has citations: [{paragraph_id, page_number, text_excerpt}, ×3]
  AND  citations are returned as part of the deep_dive_criterion event payload
```

```
AC-S9.3   UI shows clickable citation per row, modal with excerpt
GIVEN  the deep-dive panel is rendered
WHEN   the user clicks "📑 view source" on a row
THEN   a modal opens
  AND  the modal shows the top citation's text excerpt with the relevant phrase highlighted
  AND  the modal shows page_number and links to the official PDF (anchored on page if possible)
```

**Manual test**:
1. After S8, click 📑 on the "breakthrough innovation potential" criterion.
2. Modal opens with excerpt visible.
3. Cross-reference excerpt with the official EIC Accelerator 2026 work programme PDF on CINEA → exact match.

**Demo proof**: screen recording of click → modal + side-by-side with the official PDF page showing the same excerpt.

---

## AC-S10 — Lovable production frontend

```
AC-S10.1   Lovable URL completes the agent flow end-to-end
GIVEN  the Lovable project is published at <project>.lovable.app
WHEN   a user pastes a pitchdeck and clicks Run
THEN   the SSE stream from the deployed Cloud Run URL is consumed
  AND  all events render: thinking, parsed, matched, combos, plan, draft, dossier
  AND  the dossier opens in an iframe or new tab
```

```
AC-S10.2   Visual quality bar
GIVEN  the Lovable URL is open on Chrome desktop
WHEN   the user runs the agent flow
THEN   typography is consistent (single font family, not default browser fonts)
  AND  spacing follows an 8px grid
  AND  no element exhibits FOUC (flash of unstyled content)
  AND  loading/streaming states animate smoothly
  AND  on mobile (iPhone Safari), no horizontal scroll, no overflow text
```

```
AC-S10.3   Type contract from OpenAPI is enforced
GIVEN  the Lovable codebase imports types from openapi-typescript generation
WHEN   tsc runs
THEN   tsc passes
  AND  the AgentEvent discriminated union matches what fundsagent.py emits
```

**Manual test**:
1. Open the Lovable URL on Chrome desktop. Run agent. Full flow works.
2. Open same URL on iPhone Safari. Pinch zoom not needed. Page is readable.
3. In the Lovable repo, run `npm run build` → no TS errors.

**Demo proof**: side-by-side screenshots — Python URL vs Lovable URL on the same input.

---

## AC-S11 — Tests + CI

```
AC-S11.1   Unit tests pass on the matcher
GIVEN  tests/test_matcher.py is committed
WHEN   pytest tests/test_matcher.py runs
THEN   all 8 tests pass
  AND  test names map to ACs from PROJECT_SPEC.md (e.g., test_AC04_zero_eligibility)
```

```
AC-S11.2   Integration tests pass on the API
GIVEN  tests/test_api.py is committed
  AND  cerebras_chat is patched to return canned JSON
WHEN   pytest tests/test_api.py runs
THEN   all 4 tests pass
  AND  they cover AC-01 (happy path), AC-02 (ask), AC-04 (empty state), AC-07 (Cerebras down)
```

```
AC-S11.3   CI runs on every push, badge is green
GIVEN  .github/workflows/ci.yml is configured to run pytest + pyright + ruff
WHEN   a commit is pushed to main
THEN   the GitHub Actions workflow runs to completion
  AND  all three steps pass
  AND  the README badge is green
```

**Manual test**:
1. `pytest -v` locally → 12+ tests pass.
2. `pyright fundsagent.py` → 0 errors in strict mode.
3. `ruff check .` → 0 errors.
4. `git push` → GitHub Actions tab shows the run, all green within 2 minutes.

**Demo proof**: GitHub Actions run summary screenshot + README badge.

---

## AC-S12 — Smoke deploy script + checklist

```
AC-S12.1   Smoke script asserts the production URL is healthy
GIVEN  scripts/smoke_demo.sh exists
  AND  the deployed Cloud Run URL is the script argument
WHEN   ./scripts/smoke_demo.sh https://<url> is invoked
THEN   the script:
  • hits /api/health, asserts 200 + cerebras_configured=true
  • POSTs the GreenSilicon example to /api/agent/run
  • asserts a dossier link is emitted within 30 seconds
  • GETs the dossier URL, asserts 200 + content includes "Executive summary"
  AND  the script exits 0 on success, non-zero on any failure
  AND  the failure message pinpoints which check failed
```

```
AC-S12.2   Demo checklist exists and is followable
GIVEN  docs/DEMO_CHECKLIST.md is committed
THEN   it contains at least 8 actionable bullets (warmup ping, hotspot, fallback URLs, recording cached, browser pinned, etc.)
  AND  each bullet is a single short verb-led action
```

**Manual test**:
1. Run the smoke script against the live URL → exits 0 with summary.
2. Tamper with the URL (e.g., point at localhost:9999) → exits non-zero with clear message.
3. Read `DEMO_CHECKLIST.md` aloud — every line is something concrete to do.

**Demo proof**: terminal capture of green smoke run + the checklist as committed markdown.

---

## AC-S13 — Pitch deck

```
AC-S13.1   PDF exists and respects format constraints
GIVEN  pitch-deck.pdf is committed
THEN   it has at most 10 slides
  AND  it is a valid PDF (opens in any reader)
  AND  it is < 10 MB
```

```
AC-S13.2   Required content per slide is present
GIVEN  pitch-deck.pdf is opened
THEN   slide 1 contains the locked 60s message verbatim from PROJECT_SPEC.md §2
  AND  slides 2-3 contain the problem stats sourced from docs/PITCH_SOURCES.md
  AND  slides 4-6 contain demo screenshots from the deployed UI
  AND  slide 7 contains the architecture diagram from DECISIONS.md §1
  AND  slide 8 contains business model + GTM via incubateurs
  AND  slide 9 contains the 3 sponsors integrations (Cerebras, Google Cloud, Lovable)
  AND  slide 10 contains team + ask + roadmap
```

```
AC-S13.3   60-second timing is verified
GIVEN  the team rehearses the pitch
WHEN   one person reads slide 1's message at a normal pace
THEN   the timer reads ≤ 60 seconds
```

**Manual test**:
1. Open the PDF, count slides.
2. Stopwatch slide 1 message read aloud.
3. Verify each slide content per the checklist above.

**Demo proof**: PDF in repo + a recording of the team reading the pitch in 90 seconds (60s message + 30s sponsors + demo trigger).

---

## Cross-slice acceptance

Once **all 13 slices** are green, the product satisfies the 10 AC-01 to AC-10 from `PROJECT_SPEC.md §7`. Mapping:

| Spec AC | Sliced via |
|---|---|
| AC-01 happy path < 30s | S1 (deploy) + S3 (live data) + S5 (re-run path) |
| AC-02 ask on missing fields | already in `fundsagent.py:1226-1231` — covered by S11 tests |
| AC-03 what-if < 2s | S5 |
| AC-04 empty state honest | already in `fundsagent.py:_critical_missing` + tested in S11 |
| AC-05 copy share link | S6 |
| AC-06 PDF export A4 | already in `render_dossier` — covered by S11 + tested manually in S12 |
| AC-07 Cerebras fallback | already in `parse_pitchdeck:1153-1158` — covered by S11 |
| AC-08 sensitive sectors warning | dragged forward into S5 (UI panel) and tested in S11 |
| AC-09 decision-support framing | already in `render_dossier` disclaimer — verified in S13 (pitch slide) |
| AC-10 demo invariants | S12 (smoke) + S13 (rehearsal) |

When `/review` runs, it reads this file end-to-end and validates each AC ID was met by the corresponding commit.
