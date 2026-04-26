#!/usr/bin/env bash
# smoke_health.sh — minimal post-deploy health check (S1 scope)
# Slice S12 will produce the full smoke_demo.sh that runs an end-to-end agent run.
#
# Usage:
#   bash scripts/smoke_health.sh https://fundsagent-XXX.a.run.app

set -euo pipefail

URL="${1:-}"
if [[ -z "${URL}" ]]; then
  echo "Usage: $0 <BASE_URL>" >&2
  echo "Example: $0 https://fundsagent-abc123-ew.a.run.app" >&2
  exit 2
fi

URL="${URL%/}"  # strip trailing slash
HEALTH_URL="${URL}/api/health"

echo "→ GET ${HEALTH_URL}"
HTTP_CODE=$(curl --silent --show-error --max-time 30 -o /tmp/fundsagent_health.json \
  -w "%{http_code}" "${HEALTH_URL}")

if [[ "${HTTP_CODE}" != "200" ]]; then
  echo "✗ HTTP ${HTTP_CODE}" >&2
  cat /tmp/fundsagent_health.json >&2
  exit 1
fi

# Parse the JSON
PYBIN="${PYTHON:-python3}"
RESULT=$("${PYBIN}" - <<'PY' /tmp/fundsagent_health.json
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
ok_status = d.get("status") == "ok"
grants = d.get("grants_loaded", 0)
cerebras = d.get("cerebras_configured", False)
print("status_ok=" + str(int(ok_status)))
print("grants=" + str(grants))
print("cerebras=" + str(int(cerebras)))
PY
)

# shellcheck disable=SC2046
eval $(echo "${RESULT}" | sed 's/^/declare /')

if (( status_ok != 1 )); then
  echo "✗ status field is not 'ok'" >&2
  cat /tmp/fundsagent_health.json >&2
  exit 1
fi

if (( grants < 37 )); then
  echo "✗ grants_loaded=${grants}, expected ≥ 37" >&2
  exit 1
fi

if (( cerebras != 1 )); then
  echo "⚠ cerebras_configured=false — service will use heuristic fallback"
  echo "  (set CEREBRAS_API_KEY in Cloud Run env vars to enable LLM parsing)"
fi

echo "✓ ${URL}"
echo "  · status: ok"
echo "  · grants_loaded: ${grants}"
echo "  · cerebras_configured: $([[ ${cerebras} == 1 ]] && echo yes || echo no)"
