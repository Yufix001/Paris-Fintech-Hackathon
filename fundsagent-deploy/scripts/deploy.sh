#!/usr/bin/env bash
# deploy.sh — one-command Cloud Run deploy for FundsAgent
#
# Prereqs:
#   • gcloud CLI installed and authenticated (`gcloud auth login`)
#   • a GCP project with billing + Cloud Run + Cloud Build APIs enabled
#   • CEREBRAS_API_KEY exported in the current shell
#
# Usage:
#   bash scripts/deploy.sh                       # deploy with defaults
#   PROJECT_ID=my-proj REGION=europe-west1 bash scripts/deploy.sh
#   bash scripts/deploy.sh --dry-run             # print the gcloud command, do not run

set -euo pipefail

# ---- defaults ----
SERVICE_NAME="${SERVICE_NAME:-fundsagent}"
REGION="${REGION:-europe-west1}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
MIN_INSTANCES="${MIN_INSTANCES:-1}"      # 1 during pitch window, 0 off-hours
MAX_INSTANCES="${MAX_INSTANCES:-3}"
MEMORY="${MEMORY:-1Gi}"
CPU="${CPU:-1}"
TIMEOUT="${TIMEOUT:-60s}"
CONCURRENCY="${CONCURRENCY:-40}"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

# ---- preflight ----
if ! command -v gcloud >/dev/null 2>&1; then
  echo "✗ gcloud CLI not found. Install: https://cloud.google.com/sdk/docs/install" >&2
  exit 1
fi

if [[ -z "${PROJECT_ID}" ]]; then
  echo "✗ No GCP project. Run: gcloud config set project <PROJECT_ID>" >&2
  exit 1
fi

if [[ -z "${CEREBRAS_API_KEY:-}" ]]; then
  echo "⚠ CEREBRAS_API_KEY is not set in your environment."
  echo "  The service will boot but will fall back to the heuristic parser."
  echo "  Press Ctrl+C to abort, or Enter to deploy without the key."
  read -r
fi

# ---- the command ----
CMD=(
  gcloud run deploy "${SERVICE_NAME}"
  --source .
  --region "${REGION}"
  --project "${PROJECT_ID}"
  --allow-unauthenticated
  --min-instances "${MIN_INSTANCES}"
  --max-instances "${MAX_INSTANCES}"
  --memory "${MEMORY}"
  --cpu "${CPU}"
  --timeout "${TIMEOUT}"
  --concurrency "${CONCURRENCY}"
  --port 8080
)

# Env vars: only forward what's set, never echo the values.
ENV_VARS=()
if [[ -n "${CEREBRAS_API_KEY:-}" ]]; then
  ENV_VARS+=("CEREBRAS_API_KEY=${CEREBRAS_API_KEY}")
fi
if [[ -n "${CEREBRAS_MODEL:-}" ]]; then
  ENV_VARS+=("CEREBRAS_MODEL=${CEREBRAS_MODEL}")
fi
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
  ENV_VARS+=("GEMINI_API_KEY=${GEMINI_API_KEY}")
fi
if [[ "${#ENV_VARS[@]}" -gt 0 ]]; then
  IFS=','
  CMD+=( --set-env-vars "${ENV_VARS[*]}" )
  unset IFS
fi

# ---- print + run ----
echo "──────────────────────────────────────────────────────────────"
echo "FundsAgent · Cloud Run deploy"
echo "──────────────────────────────────────────────────────────────"
echo "  service:        ${SERVICE_NAME}"
echo "  region:         ${REGION}"
echo "  project:        ${PROJECT_ID}"
echo "  min/max:        ${MIN_INSTANCES}/${MAX_INSTANCES}"
echo "  memory/cpu:     ${MEMORY}/${CPU}"
echo "  cerebras key:   $([[ -n "${CEREBRAS_API_KEY:-}" ]] && echo 'set' || echo 'unset (heuristic fallback)')"
echo "  gemini key:     $([[ -n "${GEMINI_API_KEY:-}" ]] && echo 'set' || echo 'unset')"
echo "──────────────────────────────────────────────────────────────"

# Render the command without printing secrets
PRINTABLE=("${CMD[@]}")
for i in "${!PRINTABLE[@]}"; do
  if [[ "${PRINTABLE[$i]}" == "--set-env-vars" ]]; then
    PRINTABLE[$((i+1))]="$(echo "${PRINTABLE[$((i+1))]}" | sed -E 's/(KEY=)[^,]+/\1***REDACTED***/g')"
  fi
done
echo "Command:"
printf '  %s\n' "${PRINTABLE[@]}"
echo

if (( DRY_RUN )); then
  echo "(dry-run, exiting before execution)"
  exit 0
fi

# Real deploy
"${CMD[@]}"

# ---- post-deploy ----
URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --format='value(status.url)')
echo
echo "✓ Deployed: ${URL}"
echo
echo "Smoke test:"
echo "  bash scripts/smoke_health.sh ${URL}"
