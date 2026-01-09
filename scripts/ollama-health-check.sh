#!/bin/bash
# ollama-health-check.sh
# Verifies Ollama is responsive and model is available before Hestia starts.
# Returns exit code 0 if healthy, non-zero otherwise.
#
# Usage:
#   ./ollama-health-check.sh           # Basic check
#   ./ollama-health-check.sh --warm    # Check and warm up model
#   ./ollama-health-check.sh --wait    # Wait for Ollama to be ready (with timeout)
#   ./ollama-health-check.sh --json    # Output JSON status

set -euo pipefail

# Configuration
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODEL_NAME="${MODEL_NAME:-mixtral:8x7b-instruct-v0.1-q4_K_M}"
WAIT_TIMEOUT=120  # seconds to wait for Ollama
WARM_TIMEOUT=300  # seconds to wait for model warmup

# Parse arguments
DO_WARM=false
DO_WAIT=false
OUTPUT_JSON=false

for arg in "$@"; do
    case $arg in
        --warm)
            DO_WARM=true
            ;;
        --wait)
            DO_WAIT=true
            ;;
        --json)
            OUTPUT_JSON=true
            ;;
        --help|-h)
            echo "Usage: $0 [--warm] [--wait] [--json]"
            echo ""
            echo "Options:"
            echo "  --warm   Warm up the model after health check"
            echo "  --wait   Wait for Ollama to be ready (timeout: ${WAIT_TIMEOUT}s)"
            echo "  --json   Output status as JSON"
            exit 0
            ;;
    esac
done

# Output functions
output_status() {
    local status="$1"
    local ollama_available="$2"
    local model_available="$3"
    local model_loaded="$4"
    local message="$5"

    if $OUTPUT_JSON; then
        cat <<EOF
{
    "status": "${status}",
    "ollama_available": ${ollama_available},
    "model_available": ${model_available},
    "model_loaded": ${model_loaded},
    "model_name": "${MODEL_NAME}",
    "ollama_host": "${OLLAMA_HOST}",
    "message": "${message}",
    "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    else
        echo "[${status^^}] ${message}"
    fi
}

# Check if Ollama API is responding
check_ollama_api() {
    curl -s --max-time 10 "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1
}

# Check if model is available (downloaded)
check_model_available() {
    local models
    models=$(curl -s --max-time 10 "${OLLAMA_HOST}/api/tags" 2>/dev/null || echo "{}")
    echo "$models" | grep -q "${MODEL_NAME}" 2>/dev/null
}

# Check if model is currently loaded in memory
check_model_loaded() {
    local running
    running=$(curl -s --max-time 10 "${OLLAMA_HOST}/api/ps" 2>/dev/null || echo "{}")
    echo "$running" | grep -q "${MODEL_NAME}" 2>/dev/null
}

# Wait for Ollama to be ready
wait_for_ollama() {
    local start_time
    start_time=$(date +%s)

    echo "Waiting for Ollama to be ready (timeout: ${WAIT_TIMEOUT}s)..."

    while true; do
        if check_ollama_api; then
            echo "Ollama is ready."
            return 0
        fi

        local elapsed
        elapsed=$(($(date +%s) - start_time))

        if [[ $elapsed -ge $WAIT_TIMEOUT ]]; then
            echo "Timeout waiting for Ollama after ${WAIT_TIMEOUT}s"
            return 1
        fi

        sleep 2
    done
}

# Warm up the model
warm_model() {
    echo "Warming up model ${MODEL_NAME}..."

    local response
    response=$(curl -s --max-time "${WARM_TIMEOUT}" \
        -X POST "${OLLAMA_HOST}/api/generate" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"${MODEL_NAME}\",
            \"prompt\": \"ping\",
            \"stream\": false,
            \"options\": {
                \"num_predict\": 1
            }
        }" 2>&1)

    if echo "$response" | grep -q '"done":true'; then
        echo "Model warmed up successfully."
        return 0
    else
        echo "Failed to warm up model."
        return 1
    fi
}

# Main health check
main() {
    # Wait for Ollama if requested
    if $DO_WAIT; then
        if ! wait_for_ollama; then
            output_status "unhealthy" "false" "false" "false" "Ollama not available after waiting"
            exit 1
        fi
    fi

    # Check Ollama API
    if ! check_ollama_api; then
        output_status "unhealthy" "false" "false" "false" "Ollama API not responding at ${OLLAMA_HOST}"
        exit 1
    fi

    # Check model availability
    if ! check_model_available; then
        output_status "unhealthy" "true" "false" "false" "Model ${MODEL_NAME} not found"
        exit 1
    fi

    # Check if model is loaded
    local model_loaded=false
    if check_model_loaded; then
        model_loaded=true
    fi

    # Warm up model if requested
    if $DO_WARM && ! $model_loaded; then
        if warm_model; then
            model_loaded=true
        else
            output_status "degraded" "true" "true" "false" "Model available but warmup failed"
            exit 1
        fi
    fi

    # All good
    if $model_loaded; then
        output_status "healthy" "true" "true" "true" "Ollama healthy, model loaded and ready"
    else
        output_status "healthy" "true" "true" "false" "Ollama healthy, model available (not yet loaded)"
    fi
    exit 0
}

main "$@"
