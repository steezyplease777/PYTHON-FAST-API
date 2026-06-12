#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d ".venv" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

if [[ -f ".dev.vars" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".dev.vars"
  set +a
elif [[ -f ".dev.vars.example" ]]; then
  echo "Warning: .dev.vars not found. Copy .dev.vars.example to .dev.vars and fill in secrets."
  set -a
  # shellcheck disable=SC1091
  source ".dev.vars.example"
  set +a
else
  echo "Error: no .dev.vars or .dev.vars.example found."
  exit 1
fi

: "${SUPABASE_URL:?Set SUPABASE_URL in .dev.vars}"

if [[ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  echo "Warning: SUPABASE_SERVICE_ROLE_KEY is empty. Inline/download label tests will work; upload mode will fail."
  export SUPABASE_SERVICE_ROLE_KEY="local-dev-placeholder"
fi

echo "Starting local API at http://127.0.0.1:8080 (reload enabled)"
echo "Docs: http://127.0.0.1:8080/docs"
echo "Health: http://127.0.0.1:8080/health"
echo ""
echo "Example label test:"
echo '  curl -X POST http://127.0.0.1:8080/labels -H "Content-Type: application/json" -d '"'"'{"productId":"test","title":"DANE POLO - WHITE","sku":"CORE-XS","upc":"840441526871","msrp":89.99,"size":"XS","mode":"download"}'"'"' --output label.pdf'
echo ""

exec .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
