#!/bin/bash
# ollama-keepalive.sh
# Keeps Mixtral 8x7B model warm by sending periodic ping requests to Ollama.
# This prevents cold start delays when the model hasn't been used recently.
#
# Usage: Run via launchd (com.hestia.ollama-keepalive.plist) or manually.
# Interval: Every 10 minutes (configured in launchd plist)

set -euo pipefail

# Configuration
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODEL_NAME="${MODEL_NAME:-mixtral:8x7b-instruct-v0.1-q4_K_M}"
LOG_DIR="${HOME}/hestia/logs"
LOG_FILE="${LOG_DIR}/ollama-keepalive.log"
KEEPALIVE_PROMPT="ping"
MAX_RETRIES=3
RETRY_DELAY=5

# Ensure log directory exists
mkdir -p "${LOG_DIR}"

# Logging function
log() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}"
}

# Check if Ollama is running
check_ollama() {
    if curl -s --max-time 10 "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Send keepalive ping to model
send_keepalive() {
    local response
    local http_code

    # Use generate endpoint with minimal prompt to keep model loaded
    # The model will generate a short response, keeping it in memory
    response=$(curl -s --max-time 120 -w "\n%{http_code}" \
        -X POST "${OLLAMA_HOST}/api/generate" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"${MODEL_NAME}\",
            \"prompt\": \"${KEEPALIVE_PROMPT}\",
            \"stream\": false,
            \"options\": {
                \"num_predict\": 1
            }
        }" 2>&1)

    http_code=$(echo "$response" | tail -1)

    if [[ "$http_code" == "200" ]]; then
        return 0
    else
        log "ERROR" "Keepalive request failed with HTTP ${http_code}"
        return 1
    fi
}

# Main keepalive function with retry logic
do_keepalive() {
    local attempt=1

    while [[ $attempt -le $MAX_RETRIES ]]; do
        if ! check_ollama; then
            log "WARN" "Ollama not responding (attempt ${attempt}/${MAX_RETRIES})"
            if [[ $attempt -lt $MAX_RETRIES ]]; then
                sleep "$RETRY_DELAY"
                ((attempt++))
                continue
            else
                log "ERROR" "Ollama not available after ${MAX_RETRIES} attempts"
                return 1
            fi
        fi

        log "INFO" "Sending keepalive ping to ${MODEL_NAME}"

        if send_keepalive; then
            log "INFO" "Keepalive successful - model ${MODEL_NAME} is warm"
            return 0
        else
            log "WARN" "Keepalive failed (attempt ${attempt}/${MAX_RETRIES})"
            if [[ $attempt -lt $MAX_RETRIES ]]; then
                sleep "$RETRY_DELAY"
                ((attempt++))
            else
                log "ERROR" "Keepalive failed after ${MAX_RETRIES} attempts"
                return 1
            fi
        fi
    done
}

# Rotate log if too large (> 10MB)
rotate_log() {
    if [[ -f "${LOG_FILE}" ]]; then
        local size
        size=$(stat -f%z "${LOG_FILE}" 2>/dev/null || stat --printf="%s" "${LOG_FILE}" 2>/dev/null || echo 0)
        if [[ $size -gt 10485760 ]]; then
            mv "${LOG_FILE}" "${LOG_FILE}.1"
            log "INFO" "Log rotated"
        fi
    fi
}

# Main execution
main() {
    rotate_log
    log "INFO" "Starting keepalive check"

    if do_keepalive; then
        exit 0
    else
        exit 1
    fi
}

main "$@"
