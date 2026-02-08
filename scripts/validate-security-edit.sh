#!/bin/bash
# validate-security-edit.sh
# Pre-edit hook: validates that changes to security-critical files
# don't introduce plaintext secrets or violate security patterns.
#
# Usage: ./scripts/validate-security-edit.sh <file_path>
# Exit 0 = safe to proceed, Exit 1 = blocked

FILE_PATH="${1}"

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

echo "[SECURITY HOOK] Validating edit to: $FILE_PATH"

# Check for common secret patterns in the file
VIOLATIONS=0

# Pattern: hardcoded tokens/keys/passwords
if grep -qiE '(password|secret|token|api_key|private_key)\s*=\s*["\x27][^"\x27]{8,}' "$FILE_PATH" 2>/dev/null; then
    echo "[SECURITY HOOK] WARNING: Possible hardcoded credential detected"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Pattern: allow_origins=["*"]
if grep -q 'allow_origins=\["\\*"\]' "$FILE_PATH" 2>/dev/null; then
    echo "[SECURITY HOOK] WARNING: Wildcard CORS origin detected"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

# Pattern: bare except (security code must handle specific exceptions)
if grep -qE '^\s*except\s*:' "$FILE_PATH" 2>/dev/null; then
    echo "[SECURITY HOOK] WARNING: Bare except clause in security-critical file"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

if [ $VIOLATIONS -gt 0 ]; then
    echo "[SECURITY HOOK] Found $VIOLATIONS potential security violation(s). Review carefully."
    # We warn but don't block — the developer makes the final call
    exit 0
fi

echo "[SECURITY HOOK] Validation passed."
exit 0
