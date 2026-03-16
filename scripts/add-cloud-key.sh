#!/bin/bash
# Add or update a cloud provider API key on the local Hestia server.
# Usage: ./scripts/add-cloud-key.sh anthropic sk-ant-your-key-here

set -e

PROVIDER="${1:?Usage: $0 <provider> <api_key> [state]}"
API_KEY="${2:?Usage: $0 <provider> <api_key> [state]}"
STATE="${3:-enabled_full}"

TOKEN=$(security find-generic-password -s hestia-cli -a device-token -w 2>/dev/null)
if [ -z "$TOKEN" ]; then
    echo "Error: No device token in Keychain. Run 'hestia setup' first."
    exit 1
fi

AUTH="-H X-Hestia-Device-Token:$TOKEN"
BASE="https://localhost:8443/v1/cloud/providers"

# Remove existing provider first (ignore errors if not found)
curl -sk -X DELETE "$BASE/$PROVIDER" -H "X-Hestia-Device-Token: $TOKEN" > /dev/null 2>&1 || true

# Add with new key
RESULT=$(curl -sk -X POST "$BASE" \
    -H "X-Hestia-Device-Token: $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"provider\":\"$PROVIDER\",\"api_key\":\"$API_KEY\",\"state\":\"$STATE\"}")

echo "$RESULT"
echo ""
echo "Done. Use '/cloud' in the CLI to verify."
