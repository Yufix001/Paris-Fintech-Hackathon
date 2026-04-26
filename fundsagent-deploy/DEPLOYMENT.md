# DEPLOYMENT.md — Google Cloud step-by-step

> Production deployment of FundsAgent on Google Cloud, layer by layer.
> Designed for a hackathon team (2 devs + 3 designers) that may be unfamiliar
> with GCP. Every command is copy-pasteable. Every step is verifiable before
> moving on. Total elapsed time on a fresh GCP project: **~45 minutes** for
> the demo-ready stack (S1 + S2 + S3); **~2 hours** for the full stack
> (S1 → S9).

## What you are deploying

```
              ┌───────────────────────────────────────┐
              │  Lovable (Next.js)                     │
              │  https://<project>.lovable.app         │
              │  consumes /api/agent/run + iframes     │
              │           /dossier/<id>                │
              └────────────┬───────────────────────────┘
                           │ HTTPS
                           ▼
              ┌───────────────────────────────────────┐
              │  Cloud Run service: fundsagent         │ ← S1
              │  europe-west1, --min-instances=1       │
              │  reads CEREBRAS_API_KEY (Secret Mgr)    │
              │  reads GEMINI_API_KEY (Secret Mgr)      │
              └────────┬───────────────────┬──────────┘
                       │                   │
                       ▼                   ▼
        ┌──────────────────────┐  ┌──────────────────────┐
        │  Firestore (Native)   │  │  Vertex AI            │
        │  collections:         │  │  · Gemini 3 Pro       │
        │  · dossiers           │  │  · Gemini 3 Flash     │
        │  · grants_eu (22)     │  │  · text-embedding-004 │
        │  · grants_fr (15)     │  │  · Vector Search       │
        │  · call_sections      │  └──────────────────────┘
        └────────┬──────────────┘            ▲
                 ▲                           │
                 │ writes                    │ called from S4 / S7 / S8 / S9
                 │                           │
        ┌────────┴──────────────────────────┴───────┐
        │  Cloud Run Jobs (nightly via Scheduler)     │
        │  · refresh_sedia.py     (S3, EU deadlines)  │
        │  · refresh_fr.py        (S4, FR via Gemini) │
        │  · ingest_call_doc.py   (S9, PDF → vectors) │
        └─────────────────────────────────────────────┘
                       ▲
                       │
        ┌──────────────┴───────┐
        │  Cloud Scheduler      │
        │  cron 04:00 UTC daily │
        └──────────────────────┘

        Document AI Layout Parser ── used by ingest_call_doc.py (S9)
```

Cost order of magnitude for the hackathon window (Apr 25-26, 24 h pitch period):
**$3-8 of GCP credits**, dominated by Cloud Run min-instance and a few hundred
Vertex AI calls. The $300 free credit + the $5 hackathon credit cover this
multiple times over.

---

## Phase 0 — Prerequisites (10 min)

### 0.1 Accounts you need

| Service | Purpose | URL |
|---|---|---|
| Google Cloud account | the deploy target | https://console.cloud.google.com |
| Cerebras account | LLM hot-path inference | https://cloud.cerebras.ai |
| Lovable account | frontend hosting | https://lovable.dev |
| GitHub account | source code + CI | https://github.com |

### 0.2 CLI tools on the dev machine

```bash
# macOS
brew install --cask google-cloud-sdk
brew install jq curl

# Linux (Debian / Ubuntu)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
sudo apt-get install jq curl

# Verify
gcloud --version
jq --version
```

### 0.3 GCP free credits + hackathon credits

The hackathon coupon (referenced in `BRIEF.md`) tops up **$5** in addition to
the $300 standard free trial. Apply both:

1. New project automatically gets the $300 free trial if you have not used it.
2. Redeem the hackathon coupon at https://cloud.google.com/billing/docs/how-to/edu-grants

You can verify credits at **Console → Billing → Credits**.

---

## Phase 1 — Initial project setup (5 min)

### 1.1 Create the project

```bash
# Pick a globally-unique id. Use ascii lowercase + hyphens + numbers.
export PROJECT_ID="fundsagent-hck-2026"
export REGION="europe-west1"

gcloud projects create "${PROJECT_ID}" \
  --name="FundsAgent Hackathon 2026"

gcloud config set project "${PROJECT_ID}"
gcloud config set run/region "${REGION}"
gcloud config set compute/region "${REGION}"
```

### 1.2 Link the billing account

Console path: **Billing → Link a billing account → select your account**.

CLI alternative once you know the billing account id (`gcloud billing accounts list`):

```bash
export BILLING_ACCOUNT_ID="0X0X0X-0X0X0X-0X0X0X"
gcloud beta billing projects link "${PROJECT_ID}" \
  --billing-account="${BILLING_ACCOUNT_ID}"
```

### 1.3 Enable the APIs (one command)

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  cloudscheduler.googleapis.com \
  aiplatform.googleapis.com \
  documentai.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

This takes 1-2 minutes. Verify with:

```bash
gcloud services list --enabled --filter="name~run|firestore|aiplatform|documentai|scheduler|secretmanager"
```

---

## Phase 2 — Secrets and IAM (5 min)

### 2.1 Store API keys in Secret Manager

```bash
# Cerebras key
echo -n "csk-XXXXXXXXXXXXXXXXX" | \
  gcloud secrets create cerebras-api-key \
    --data-file=- \
    --replication-policy=automatic

# Gemini key (will be created later in Phase 5; placeholder for now)
echo -n "AIzaSyXXXXXXXXXXXXXXXXXX" | \
  gcloud secrets create gemini-api-key \
    --data-file=- \
    --replication-policy=automatic

# Verify
gcloud secrets list
```

### 2.2 Create the runtime service account

```bash
gcloud iam service-accounts create fundsagent-runtime \
  --display-name="FundsAgent Cloud Run runtime"

export SA_EMAIL="fundsagent-runtime@${PROJECT_ID}.iam.gserviceaccount.com"

# Grants needed:
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"            # Firestore read/write

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user"           # Vertex AI Gemini calls

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/documentai.apiUser"        # Document AI Layout Parser

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"
```

### 2.3 Create the deployer (CI / human) service account *(optional)*

For the hackathon, deploying as your personal user is fine (`gcloud auth login`).
If you want a CI-bound deploy:

```bash
gcloud iam service-accounts create fundsagent-deployer \
  --display-name="FundsAgent CI deployer"

export DEPLOYER_EMAIL="fundsagent-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

for ROLE in \
  roles/run.admin \
  roles/iam.serviceAccountUser \
  roles/cloudbuild.builds.editor \
  roles/secretmanager.admin
do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${DEPLOYER_EMAIL}" \
    --role="${ROLE}"
done

# Download a key (for GitHub Actions OIDC is preferred; key here is the simple path)
gcloud iam service-accounts keys create ~/fundsagent-deployer-key.json \
  --iam-account="${DEPLOYER_EMAIL}"
```

---

## Phase 3 — Cloud Run for the engine (Slice S1) (10 min)

Artifacts already prepared in the repo: `Dockerfile`, `.gcloudignore`,
`scripts/deploy.sh`, `scripts/smoke_health.sh`. The deploy reduces to:

### 3.1 First deploy

```bash
cd ~/Plugin
gcloud auth login                                # browser, one-time
gcloud config set project "${PROJECT_ID}"

# Read the secret out (or pass via the script's env var)
export CEREBRAS_API_KEY="$(gcloud secrets versions access latest --secret=cerebras-api-key)"

bash scripts/deploy.sh
```

The script wraps:

```text
gcloud run deploy fundsagent
  --source .
  --region europe-west1
  --allow-unauthenticated
  --min-instances 1                # warm during pitch window
  --max-instances 3
  --memory 1Gi
  --cpu 1
  --timeout 60s
  --concurrency 40
  --port 8080
  --set-env-vars CEREBRAS_API_KEY=...
```

First build takes 2-3 minutes (Cloud Build pulls base image + pip install +
push to Artifact Registry). Subsequent deploys: 30-60 seconds.

### 3.2 Bind the runtime service account

```bash
gcloud run services update fundsagent \
  --service-account="${SA_EMAIL}" \
  --region="${REGION}"
```

### 3.3 Replace plain env var with Secret Manager mount

This is the production-grade pattern: secrets do not appear in the service
revision spec.

```bash
gcloud run services update fundsagent \
  --region="${REGION}" \
  --remove-env-vars CEREBRAS_API_KEY \
  --update-secrets="CEREBRAS_API_KEY=cerebras-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest"
```

### 3.4 Smoke test

```bash
URL=$(gcloud run services describe fundsagent --region="${REGION}" --format='value(status.url)')
echo "${URL}"
bash scripts/smoke_health.sh "${URL}"
```

**Expected**: `✓ <URL>` with `cerebras_configured=true`, `grants_loaded=37`.

If `cerebras_configured=false`, the secret was not propagated. Check
**Console → Cloud Run → fundsagent → Variables & Secrets**.

### 3.5 First end-to-end demo on the live URL

Open `${URL}` in the browser. Click **Example: GreenSilicon** then **▶ Run agent**.
The full flow should complete in ~3 seconds (cold start tolerated on the very
first request after deploy).

This is when **AC-S1.1** and **AC-S1.2** get marked green.

---

## Phase 4 — Firestore for persistence (Slice S2) (10 min)

### 4.1 Provision the database

Firestore in **Native mode** is what you want (the older Datastore mode is more
restrictive). Once set, the mode is permanent for the project — choose Native.

```bash
gcloud firestore databases create \
  --location="${REGION}" \
  --type=firestore-native
```

### 4.2 Create indexes for the collections you query

```bash
# Ad-hoc indexes can be defined later. For the hackathon the default
# single-field indexing is enough; the collections are queried by document id
# (the dossier token, the grant_id), which Firestore indexes by default.
echo "No composite indexes needed for the demo flow."
```

### 4.3 Test from local

```bash
# Use gcloud auth application default for local dev
gcloud auth application-default login

python3 - <<'PY'
from google.cloud import firestore
db = firestore.Client(project="fundsagent-hck-2026")
doc = db.collection("dossiers").document("test").set({"ping": "pong"})
print("written")
print(db.collection("dossiers").document("test").get().to_dict())
db.collection("dossiers").document("test").delete()
print("deleted")
PY
```

If the three lines print, Firestore is reachable from your machine. The
Cloud Run runtime has the same access via its bound service account.

### 4.4 Wire `fundsagent.py` to Firestore

This is **slice S2** in `ROADMAP.md`. The change replaces the in-memory
`DOSSIER_STORE` dict with a `FirestoreDossierStore` adapter exposing the same
two methods (`set`, `get`). The schema:

```text
dossiers/{token} = {
  deck:        Pitchdeck,
  matches:     GrantMatch[],
  combos:      Combo[],
  plan:        FinancingPlan,
  draft:       { grant: str, text: str } | null,
  stats:       Stats,
  generated_at: ISO8601
}
```

After the slice ships, redeploy:

```bash
bash scripts/deploy.sh
bash scripts/smoke_health.sh "${URL}"
```

**Verification (AC-S2.1)**: generate a dossier, redeploy, the link still works.

---

## Phase 5 — Vertex AI for Gemini and embeddings (10 min)

### 5.1 Get a Gemini API key

You have two paths.

**Path A — AI Studio key** (simplest, free tier covers the hackathon):

1. Go to https://aistudio.google.com → **Get API key** → **Create API key in new project**
2. Copy the `AIza...` key
3. Push it to Secret Manager:

```bash
echo -n "AIzaSyXXXXXXXXXXXXXXXXXX" | \
  gcloud secrets versions add gemini-api-key --data-file=-
```

**Path B — Vertex AI** (production pattern, no key, IAM-based auth):

The runtime service account already has `aiplatform.user`. The Python client
authenticates via Application Default Credentials (already mounted on Cloud Run).
No key to manage. Use this path for the nightly batch jobs (Phases 6 & 7).

### 5.2 Verify Gemini calls work from your machine

```bash
gcloud auth application-default login

python3 - <<'PY'
from google import genai
client = genai.Client(vertexai=True, project="fundsagent-hck-2026", location="europe-west1")
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with the single word OK and nothing else."
)
print(resp.text)
PY
```

**Expected**: `OK`. If you see authentication errors, re-run
`gcloud auth application-default login`.

### 5.3 Provision Vector Search index *(only needed for slice S9)*

```bash
# Firestore Vector Search uses a special index spec. Create via the Console for
# the demo (UI is fastest); the CLI requires a JSON manifest.
# Console → Firestore → Indexes → Single field → Add vector index
# Collection group: call_sections
# Field: embedding
# Dimensions: 768 (text-embedding-004)
# Distance: COSINE

echo "Done in the Console — see screenshot in docs/firestore-vector-index.png"
```

---

## Phase 6 — Cloud Run Jobs for nightly data refresh (Slices S3 + S4) (15 min)

### 6.1 SEDIA refresh job (Slice S3)

Once the slice is shipped, you have `scripts/refresh_sedia.py`. Deploy it as
a Cloud Run Job:

```bash
gcloud run jobs deploy refresh-sedia \
  --source . \
  --command python3 \
  --args scripts/refresh_sedia.py \
  --region "${REGION}" \
  --service-account "${SA_EMAIL}" \
  --memory 512Mi \
  --task-timeout 600s \
  --max-retries 2 \
  --update-secrets="CEREBRAS_API_KEY=cerebras-api-key:latest,GEMINI_API_KEY=gemini-api-key:latest"

# Test it once manually
gcloud run jobs execute refresh-sedia --region "${REGION}" --wait

# Verify Firestore now has 22 docs in grants_eu
python3 - <<'PY'
from google.cloud import firestore
db = firestore.Client(project="fundsagent-hck-2026")
n = sum(1 for _ in db.collection("grants_eu").stream())
print(f"grants_eu has {n} docs")
PY
```

### 6.2 French CSV refresh job (Slice S4)

```bash
gcloud run jobs deploy refresh-fr \
  --source . \
  --command python3 \
  --args scripts/refresh_fr.py \
  --region "${REGION}" \
  --service-account "${SA_EMAIL}" \
  --memory 1Gi \
  --task-timeout 900s \
  --max-retries 2 \
  --update-secrets="GEMINI_API_KEY=gemini-api-key:latest"

gcloud run jobs execute refresh-fr --region "${REGION}" --wait
```

### 6.3 Schedule both nightly via Cloud Scheduler

```bash
# SEDIA: 04:00 UTC daily
gcloud scheduler jobs create http refresh-sedia-daily \
  --location "${REGION}" \
  --schedule "0 4 * * *" \
  --uri "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/refresh-sedia:run" \
  --http-method POST \
  --oauth-service-account-email "${SA_EMAIL}"

# FR CSV: 04:30 UTC daily (slightly offset to avoid co-running)
gcloud scheduler jobs create http refresh-fr-daily \
  --location "${REGION}" \
  --schedule "30 4 * * *" \
  --uri "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/refresh-fr:run" \
  --http-method POST \
  --oauth-service-account-email "${SA_EMAIL}"

# Trigger both immediately to verify
gcloud scheduler jobs run refresh-sedia-daily --location "${REGION}"
gcloud scheduler jobs run refresh-fr-daily --location "${REGION}"
```

The runtime service account needs `roles/run.invoker` on the jobs:

```bash
for JOB in refresh-sedia refresh-fr; do
  gcloud run jobs add-iam-policy-binding "${JOB}" \
    --region "${REGION}" \
    --member "serviceAccount:${SA_EMAIL}" \
    --role roles/run.invoker
done
```

---

## Phase 7 — Document AI for the deep-dive PDF ingestion (Slice S9) (15 min)

### 7.1 Create a Layout Parser processor

Console path: **Document AI → Workbench → Create processor → Layout Parser →
europe-west1**. Note the processor id (looks like `1a2b3c4d5e6f7g8h`).

CLI alternative:

```bash
gcloud documentai processors create \
  --location="${REGION}" \
  --display-name="fundsagent-layout-parser" \
  --type=LAYOUT_PARSER_PROCESSOR

# List to find the id
gcloud documentai processors list --location="${REGION}"
```

Save the processor id as a Cloud Run env var:

```bash
gcloud run services update fundsagent \
  --region="${REGION}" \
  --update-env-vars="DOCAI_PROCESSOR_ID=projects/${PROJECT_ID}/locations/${REGION}/processors/<ID>"
```

### 7.2 One-off ingestion of the EIC Accelerator work programme PDF

After Slice S9 ships, `scripts/ingest_call_doc.py` is invoked manually once
per call doc to populate the vector store:

```bash
python3 scripts/ingest_call_doc.py \
  --pdf-url https://eic.ec.europa.eu/system/files/2026-01/EIC_Work_Programme_2026.pdf \
  --grant-id eic_accelerator
```

Verify in Firestore:

```bash
python3 - <<'PY'
from google.cloud import firestore
db = firestore.Client()
n = sum(1 for _ in db.collection("call_sections").where("grant_id", "==", "eic_accelerator").stream())
print(f"call_sections for eic_accelerator: {n}")
PY
```

Expect ≥ 40 sections.

---

## Phase 8 — Lovable frontend (Slice S10) (15 min)

The Lovable project is built separately by the design team. The deploy
amounts to wiring it to the Cloud Run URL.

### 8.1 Set the API URL in Lovable

In the Lovable editor:

1. **Project settings → Environment variables → Add variable**
   - Name: `NEXT_PUBLIC_API_BASE_URL`
   - Value: `https://fundsagent-XXXX-ew.a.run.app` (the URL from Phase 3.4)

2. The frontend reads `process.env.NEXT_PUBLIC_API_BASE_URL` for every fetch
   call. No hard-coded URLs in the source.

### 8.2 Allow CORS from Lovable on the Cloud Run service

Add to `fundsagent.py` (slice S10 task):

```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.lovable.app",
        "https://*.lovableproject.com",
        "http://localhost:3000",      # local Lovable dev
    ],
    allow_origin_regex=r"https://.*\.lovable\.(app|dev|project\.com)",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

Redeploy:

```bash
bash scripts/deploy.sh
```

### 8.3 Generate TypeScript types from OpenAPI

In the Lovable project:

```bash
npm install -D openapi-typescript
npx openapi-typescript \
  https://fundsagent-XXXX-ew.a.run.app/openapi.json \
  -o src/types/api.ts
```

Commit `src/types/api.ts`. The Lovable code imports from there:

```ts
import type { components } from "@/types/api";
type AgentEvent = components["schemas"]["AgentEvent"];
```

### 8.4 Publish

In Lovable: **Publish → Deploy**. The URL becomes
`https://<project>.lovable.app`. This URL is what you put on slide 1 of the
pitch deck.

---

## Phase 9 — Custom domain *(optional, ~30 min)*

If you have a domain (e.g., `fundsagent.app`):

```bash
gcloud beta run domain-mappings create \
  --service fundsagent \
  --domain api.fundsagent.app \
  --region "${REGION}"

# It prints the DNS records you need to add at your registrar
# (TXT for verification, A/AAAA or CNAME for routing).
# TLS is auto-provisioned by Google once DNS resolves.
```

Then update Lovable's `NEXT_PUBLIC_API_BASE_URL` to `https://api.fundsagent.app`.

For the hackathon, the default `*.run.app` URL is fine.

---

## Phase 10 — Monitoring, logs, alerts (5 min)

### 10.1 Live logs during the pitch

```bash
gcloud run services logs tail fundsagent \
  --region "${REGION}" \
  --format='value(textPayload)'
```

Keep this in a terminal during the pitch. If anything goes wrong on stage you
see it.

### 10.2 Create an uptime check

Console path: **Monitoring → Uptime checks → Create**.
- Target: `https://fundsagent-XXXX-ew.a.run.app/api/health`
- Frequency: 1 minute
- Alert email: your team's address

If `/api/health` returns non-200 for 2 minutes, you get an email. Useful in
the 4-hour window before the pitch.

### 10.3 Set a budget alert

Console path: **Billing → Budgets & alerts → Create budget**.
- Amount: $30
- Alerts at 50%, 90%, 100%

Keeps the team from accidentally burning the credits with a runaway loop.

---

## Cost estimate (24-hour pitch window)

| Service | Usage | Estimated cost |
|---|---|---|
| Cloud Run (`fundsagent`) | min-instances=1, 24h × 1 vCPU + 1 GiB | ~$1.20 |
| Cloud Run Jobs (refresh) | 2 jobs × 1 run × ~3 min each | < $0.05 |
| Cloud Build | ~5 deploys × 2 min | < $0.10 |
| Firestore | < 100 reads + writes / day | < $0.01 |
| Vertex AI Gemini | ~30 deep-dive runs × ~3k tokens | ~$0.50 |
| Document AI Layout | 1 ingestion × 50 pages | ~$0.30 |
| Cloud Scheduler | 60 jobs / month | $0.10 fixed |
| Logging + Monitoring | ~50 MB logs | < $0.10 |
| Cerebras inference | covered separately by Cerebras free tier | $0.00 |
| Secret Manager | 4 secrets, 0 rotations | < $0.10 |
| **Total** | | **~$3 / day** |

You have a $300 + $5 = $305 budget. The 24-hour hackathon window costs ~$3.
After the pitch, drop `--min-instances=0` to bring Cloud Run to scale-to-zero
and the daily cost falls to <$0.50.

---

## Rollback procedures

### A — Roll back a bad Cloud Run revision

Each `gcloud run deploy` creates a numbered revision. Roll back to the previous
one:

```bash
# List revisions
gcloud run revisions list --service fundsagent --region "${REGION}"

# Route 100% traffic back to a known-good revision
gcloud run services update-traffic fundsagent \
  --region "${REGION}" \
  --to-revisions fundsagent-00007-abc=100
```

This is your demo-day insurance. If a last-minute commit breaks the deploy,
you have the URL pointing back to the working revision in 5 seconds.

### B — Disable a misbehaving Scheduler job

```bash
gcloud scheduler jobs pause refresh-sedia-daily --location "${REGION}"
# … fix the bug, redeploy the job, then:
gcloud scheduler jobs resume refresh-sedia-daily --location "${REGION}"
```

### C — Rotate a leaked Cerebras key

```bash
echo -n "csk-NEW-KEY" | gcloud secrets versions add cerebras-api-key --data-file=-
gcloud run services update fundsagent --region "${REGION}"   # forces revision pickup
```

The previous secret version is automatically marked superseded; the runtime
fetches `:latest` on the next request.

---

## Troubleshooting

### `cloud build` fails with `permission denied`

```
ERROR: failed to create container image: unable to upload artifact: permission denied
```

The Cloud Build service account is missing `roles/artifactregistry.writer` or
`roles/run.developer`. Apply:

```bash
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
CB_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/run.developer"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/iam.serviceAccountUser"
```

### `/api/health` returns `cerebras_configured: false` after deploy

Either the secret binding did not propagate, or the secret value is empty.

```bash
gcloud secrets versions access latest --secret=cerebras-api-key | head -c 4
# expects "csk-"
gcloud run services describe fundsagent --region "${REGION}" \
  --format='value(spec.template.spec.containers[0].env)'
```

If the env shows nothing, re-apply Phase 3.3.

### Cold start > 5 seconds

Means `--min-instances` is set to 0 or you redeployed and the warm instance
was killed. Force a warmup:

```bash
URL=$(gcloud run services describe fundsagent --region "${REGION}" --format='value(status.url)')
for i in 1 2 3; do curl -sS "${URL}/api/health" > /dev/null; done
echo "warm"
```

Run this 30 seconds before the pitch.

### Vertex AI returns `403 PermissionDenied`

The runtime service account is missing `roles/aiplatform.user`. Re-apply
Phase 2.2 step 2.

### Firestore writes fail with `FAILED_PRECONDITION`

You're hitting Firestore in Datastore mode. Check:

```bash
gcloud firestore databases describe --database="(default)"
```

If `type` is `DATASTORE_MODE`, you cannot use Native API. Either delete the
database (only works on a fresh project) or create a named non-default
database in Native mode and set `FIRESTORE_DATABASE` env var on Cloud Run.

### `gcloud run deploy --source .` is slow

First build is 2-3 minutes. Subsequent builds reuse the cached pip layer and
run in 30-60 seconds. If you change `Dockerfile` (e.g., add a dep), the cache
is invalidated and it goes back to 2-3 minutes — plan for it.

### Lovable preview can fetch the API but production cannot

CORS. Re-check Phase 8.2 and confirm the Lovable production hostname matches
the regex in `allow_origin_regex`.

---

## Demo-day runbook (the 30-minute pre-pitch)

This is the script the team runs **30 minutes before** going on stage.

```bash
# 1. Confirm Cloud Run is warm
URL=$(gcloud run services describe fundsagent --region "${REGION}" --format='value(status.url)')
for i in 1 2 3; do curl -sS "${URL}/api/health" > /dev/null; done
bash scripts/smoke_health.sh "${URL}"

# 2. Confirm Firestore has fresh data
python3 - <<'PY'
from google.cloud import firestore
db = firestore.Client()
import datetime as dt
fresh = [d for d in db.collection("grants_eu").stream()
         if (dt.datetime.now(dt.timezone.utc) - d.to_dict()["last_verified_at"].astimezone(dt.timezone.utc)).total_seconds() < 86400]
print(f"EU grants refreshed in last 24 h: {len(fresh)}")
PY

# 3. Open the Lovable URL in two browser tabs (primary + fallback)
open "https://<project>.lovable.app"           # primary
open "${URL}"                                  # fallback (Python HTML)

# 4. Open Cloud Logging in a separate terminal
gcloud run services logs tail fundsagent --region "${REGION}"

# 5. Connect phone hotspot in Wi-Fi settings
# 6. Test the demo flow once on stage Wi-Fi
# 7. Open the cached recording in case (1) and (2) both fail
```

---

## Document update process

When a slice ships and adds a new GCP resource, the dev who shipped it
appends a one-line note to **§ Phase X** of this file. The team reads
DEPLOYMENT.md as the up-to-date source of truth — any drift between the
running system and this file is a bug.

Last verified: **2026-04-25 · S1 deploy artifacts ready**.
