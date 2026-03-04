#!/bin/bash
# validate-security-edit.sh
# Pre-edit hook: validates that changes to security-critical files
# don't introduce plaintext secrets or violate security patterns.
#
# Usage (CLI):   ./scripts/validate-security-edit.sh <file_path>
# Usage (hook):  Called by Claude Code PreToolUse hook — reads JSON from stdin
#
# Exit 0 = safe to proceed
# Exit 2 = blocked (PreToolUse denial — Claude Code will reject the edit)

# Dual-mode: CLI argument or Claude Code hook stdin JSON
HOOK_MODE=false
NEW_CONTENT=""

if [ -n "$1" ]; then
    FILE_PATH="$1"
else
    # Claude Code hook mode: read JSON from stdin
    HOOK_MODE=true
    INPUT=$(cat)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
    # Extract new content being written (new_string for Edit, content for Write)
    NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty' 2>/dev/null)
    if [ -z "$FILE_PATH" ]; then
        exit 0  # No file path available
    fi
fi

# Only validate security-critical paths
SECURITY_PATHS=(
    "hestia/security/"
    "hestia/api/middleware/auth.py"
    "hestia/api/server.py"
    "hestia/cloud/manager.py"
    "hestia/cloud/client.py"
    "hestia/inference/client.py"
    "hestia/api/routes/cloud.py"
    "hestia/api/routes/auth.py"
    "hestia/api/routes/files.py"
    "hestia/api/invite_store.py"
    "hestia/files/"
    "scripts/generate-cert.sh"
    ".claude/agents/"
    ".claude/settings"
)

IS_SECURITY_FILE=false
for pattern in "${SECURITY_PATHS[@]}"; do
    if [[ "$FILE_PATH" == *"$pattern"* ]]; then
        IS_SECURITY_FILE=true
        break
    fi
done

if [ "$IS_SECURITY_FILE" = false ]; then
    exit 0  # Not a security file, no validation needed
fi

echo "[SECURITY HOOK] Validating edit to: $FILE_PATH" >&2

VIOLATIONS=0
REASONS=""

# Check new content being introduced (hook mode) or file on disk (CLI mode)
if [ -n "$NEW_CONTENT" ]; then
    CHECK_SOURCE="$NEW_CONTENT"
else
    CHECK_SOURCE=$(cat "$FILE_PATH" 2>/dev/null)
fi

# Pattern: hardcoded tokens/keys/passwords
if echo "$CHECK_SOURCE" | grep -qiE '(password|secret|token|api_key|private_key)\s*=\s*["\x27][^"\x27]{8,}'; then
    REASONS="${REASONS}Possible hardcoded credential detected. "
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Pattern: allow_origins=["*"]
if echo "$CHECK_SOURCE" | grep -q 'allow_origins=\["\\*"\]'; then
    REASONS="${REASONS}Wildcard CORS origin detected. "
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Pattern: bare except (security code must handle specific exceptions)
if echo "$CHECK_SOURCE" | grep -qE '^\s*except\s*:'; then
    REASONS="${REASONS}Bare except clause in security-critical file. "
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Pattern: raw exception in HTTP response detail
if echo "$CHECK_SOURCE" | grep -qE 'detail\s*=\s*str\(e\)'; then
    REASONS="${REASONS}Raw exception in HTTP response (use sanitize_for_log). "
    VIOLATIONS=$((VIOLATIONS + 1))
fi

if [ $VIOLATIONS -gt 0 ]; then
    echo "[SECURITY HOOK] Found $VIOLATIONS potential security violation(s): $REASONS" >&2

    if [ "$HOOK_MODE" = true ]; then
        # Block the edit in Claude Code with a denial JSON
        echo "{\"decision\":\"block\",\"reason\":\"Security validation failed: ${REASONS}\"}" >&2
        exit 2
    else
        # CLI mode: warn but don't block
        echo "[SECURITY HOOK] Review carefully before proceeding."
        exit 0
    fi
fi

echo "[SECURITY HOOK] Validation passed." >&2
exit 0
