#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/pull_models.sh
#
# Pulls the embedding model (bge-m3) and the LLM (gemma:4b) into Ollama.
# Run AFTER `docker compose up -d` and after Ollama is healthy.
#
# Usage:
#   bash scripts/pull_models.sh
#   OLLAMA_BASE_URL=http://localhost:11434 bash scripts/pull_models.sh
#
# On Windows (Git Bash / WSL): run exactly as above.
# If Ollama is running on host (not in Docker), set OLLAMA_BASE_URL accordingly.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
EMBED_MODEL="${EMBED_MODEL:-bge-m3}"
LLM_MODEL="${LLM_MODEL:-gemma:2b}"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  StudyBuddy — pulling Ollama models"
echo "  Ollama URL : ${OLLAMA_BASE_URL}"
echo "  Embed model: ${EMBED_MODEL}"
echo "  LLM model  : ${LLM_MODEL}"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── Wait for Ollama to be ready ───────────────────────────────────────────────
echo "Waiting for Ollama to be reachable..."
for i in $(seq 1 30); do
    if curl -sf "${OLLAMA_BASE_URL}/api/tags" > /dev/null 2>&1; then
        echo "✅ Ollama is up."
        break
    fi
    echo "  ... attempt ${i}/30, retrying in 5s"
    sleep 5
    if [ "$i" -eq 30 ]; then
        echo "❌ Ollama did not become ready in 150s. Is Docker running?"
        exit 1
    fi
done

# ── Pull embedding model ──────────────────────────────────────────────────────
echo ""
echo "Pulling embedding model: ${EMBED_MODEL}  (~1.2 GB, may take a few minutes)"
curl -s -X POST "${OLLAMA_BASE_URL}/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${EMBED_MODEL}\", \"stream\": false}" \
    | python3 -c "import sys, json; r=json.load(sys.stdin); print('✅ ' + r.get('status','done'))" \
    || { echo "⚠️  Pull returned non-JSON or error — check Ollama logs"; }

# ── Pull LLM model ────────────────────────────────────────────────────────────
echo ""
echo "Pulling LLM model: ${LLM_MODEL}  (~2.5 GB, this will take a while on first run)"
curl -s -X POST "${OLLAMA_BASE_URL}/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${LLM_MODEL}\", \"stream\": false}" \
    | python3 -c "import sys, json; r=json.load(sys.stdin); print('✅ ' + r.get('status','done'))" \
    || { echo "⚠️  Pull returned non-JSON or error — check Ollama logs"; }

# ── Confirm ───────────────────────────────────────────────────────────────────
echo ""
echo "Models currently in Ollama:"
curl -s "${OLLAMA_BASE_URL}/api/tags" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = data.get('models', [])
if not models:
    print('  (none)')
for m in models:
    size_gb = m.get('size', 0) / 1e9
    print(f'  • {m[\"name\"]}  ({size_gb:.1f} GB)')
"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Done. Run python scripts/verify_infra.py to verify."
echo "═══════════════════════════════════════════════════════"
