#!/bin/bash
# Hestia API Test Script
# Run this to verify the API is working correctly

set -e

BASE_URL="${HESTIA_API_URL:-https://localhost:8443}"
TOKEN=""

# TLS: Hestia uses self-signed certs for local/Tailscale access.
# Use -k in development; in production, specify HESTIA_CA_CERT for proper verification.
CURL_OPTS=""
if [[ "$BASE_URL" == https://* ]]; then
    if [[ -n "${HESTIA_CA_CERT:-}" ]]; then
        CURL_OPTS="--cacert $HESTIA_CA_CERT"
    else
        CURL_OPTS="-k"
        echo -e "${YELLOW}NOTE: Using -k for self-signed cert (set HESTIA_CA_CERT for proper TLS)${NC}"
    fi
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "Hestia API Test Script"
echo "Base URL: $BASE_URL"
echo "======================================"
echo ""

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        exit 1
    fi
}

# Test 1: Ping
echo "Test 1: Ping endpoint"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" "$BASE_URL/v1/ping")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "Ping endpoint"
else
    print_result 1 "Ping endpoint (HTTP $HTTP_CODE)"
fi

# Test 2: Health check
echo ""
echo "Test 2: Health check endpoint"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" "$BASE_URL/v1/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "Health check endpoint"
    echo "  Health status:"
    echo "$RESPONSE" | head -n1 | python3 -m json.tool 2>/dev/null || echo "$RESPONSE" | head -n1
else
    print_result 1 "Health check endpoint (HTTP $HTTP_CODE)"
fi

# Test 3: Register device
echo ""
echo "Test 3: Register device"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" -X POST "$BASE_URL/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"device_name": "test-device", "device_type": "cli-test"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "Device registration"
    TOKEN=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])" 2>/dev/null)
    DEVICE_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['device_id'])" 2>/dev/null)
    echo "  Device ID: $DEVICE_ID"
    echo "  Token: ${TOKEN:0:50}..."
else
    print_result 1 "Device registration (HTTP $HTTP_CODE)"
fi

# Test 4: Get current mode (with auth)
echo ""
echo "Test 4: Get current mode (requires auth)"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" "$BASE_URL/v1/mode" \
    -H "X-Hestia-Device-Token: $TOKEN")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "Get current mode"
    echo "  Mode info:"
    echo "$RESPONSE" | head -n1 | python3 -m json.tool 2>/dev/null || echo "$RESPONSE" | head -n1
else
    print_result 1 "Get current mode (HTTP $HTTP_CODE)"
fi

# Test 5: Switch mode
echo ""
echo "Test 5: Switch to Mira mode"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" -X POST "$BASE_URL/v1/mode/switch" \
    -H "Content-Type: application/json" \
    -H "X-Hestia-Device-Token: $TOKEN" \
    -d '{"mode": "mira"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "Switch mode"
else
    print_result 1 "Switch mode (HTTP $HTTP_CODE)"
fi

# Test 6: Get staged memory
echo ""
echo "Test 6: Get staged memory"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" "$BASE_URL/v1/memory/staged" \
    -H "X-Hestia-Device-Token: $TOKEN")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "Get staged memory"
else
    print_result 1 "Get staged memory (HTTP $HTTP_CODE)"
fi

# Test 7: List tools
echo ""
echo "Test 7: List tools"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" "$BASE_URL/v1/tools" \
    -H "X-Hestia-Device-Token: $TOKEN")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "List tools"
    TOOL_COUNT=$(echo "$RESPONSE" | head -n1 | python3 -c "import sys, json; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo "?")
    echo "  Tool count: $TOOL_COUNT"
else
    echo -e "${YELLOW}  SKIP${NC}: List tools returned HTTP $HTTP_CODE (may need Apple CLI tools installed)"
fi

# Test 8: Create session
echo ""
echo "Test 8: Create session"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" -X POST "$BASE_URL/v1/sessions" \
    -H "Content-Type: application/json" \
    -H "X-Hestia-Device-Token: $TOKEN" \
    -d '{"mode": "tia"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "Create session"
    SESSION_ID=$(echo "$BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])" 2>/dev/null)
    echo "  Session ID: $SESSION_ID"
else
    print_result 1 "Create session (HTTP $HTTP_CODE)"
fi

# Test 9: Send chat message (optional - requires Ollama running)
echo ""
echo "Test 9: Send chat message"
echo -e "${YELLOW}  Note: This test requires Ollama to be running with Mixtral${NC}"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" -X POST "$BASE_URL/v1/chat" \
    -H "Content-Type: application/json" \
    -H "X-Hestia-Device-Token: $TOKEN" \
    -d "{\"message\": \"Hello Tia, respond with just 'Hello from Hestia!' and nothing else.\", \"session_id\": \"$SESSION_ID\"}" \
    --max-time 120)
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "Send chat message"
    echo "  Response:"
    echo "$RESPONSE" | head -n1 | python3 -m json.tool 2>/dev/null || echo "$RESPONSE" | head -n1
elif [ "$HTTP_CODE" = "000" ]; then
    echo -e "${YELLOW}  SKIP${NC}: Chat test timed out (Ollama may not be running)"
else
    print_result 1 "Send chat message (HTTP $HTTP_CODE)"
fi

# Test 10: Cloud - List providers (should return empty list)
echo ""
echo "Test 10: List cloud providers"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" "$BASE_URL/v1/cloud/providers" \
    -H "X-Hestia-Device-Token: $TOKEN")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "List cloud providers"
    PROVIDER_COUNT=$(echo "$RESPONSE" | head -n1 | python3 -c "import sys, json; print(json.load(sys.stdin)['count'])" 2>/dev/null || echo "?")
    CLOUD_STATE=$(echo "$RESPONSE" | head -n1 | python3 -c "import sys, json; print(json.load(sys.stdin)['cloud_state'])" 2>/dev/null || echo "?")
    echo "  Providers: $PROVIDER_COUNT, Cloud state: $CLOUD_STATE"
else
    print_result 1 "List cloud providers (HTTP $HTTP_CODE)"
fi

# Test 11: Cloud - Get usage summary
echo ""
echo "Test 11: Cloud usage summary"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" "$BASE_URL/v1/cloud/usage?period_days=7" \
    -H "X-Hestia-Device-Token: $TOKEN")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    print_result 0 "Cloud usage summary"
    TOTAL_REQUESTS=$(echo "$RESPONSE" | head -n1 | python3 -c "import sys, json; print(json.load(sys.stdin)['total_requests'])" 2>/dev/null || echo "?")
    TOTAL_COST=$(echo "$RESPONSE" | head -n1 | python3 -c "import sys, json; print(json.load(sys.stdin)['total_cost_usd'])" 2>/dev/null || echo "?")
    echo "  Requests: $TOTAL_REQUESTS, Cost: \$$TOTAL_COST"
else
    print_result 1 "Cloud usage summary (HTTP $HTTP_CODE)"
fi

# Test 12: Cloud - Add provider (with dummy key, should fail validation)
echo ""
echo "Test 12: Cloud add provider (short key rejection)"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" -X POST "$BASE_URL/v1/cloud/providers" \
    -H "Content-Type: application/json" \
    -H "X-Hestia-Device-Token: $TOKEN" \
    -d '{"provider": "anthropic", "api_key": "short", "state": "enabled_smart"}')
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "400" ]; then
    print_result 0 "Short API key correctly rejected (400)"
else
    print_result 1 "Short API key should return 400 (got HTTP $HTTP_CODE)"
fi

# Test 13: Cloud - Health check for non-existent provider
echo ""
echo "Test 13: Cloud health check (non-existent provider)"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" -X POST "$BASE_URL/v1/cloud/providers/anthropic/health" \
    -H "Content-Type: application/json" \
    -H "X-Hestia-Device-Token: $TOKEN")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "404" ]; then
    print_result 0 "Health check for missing provider returns 404"
else
    print_result 1 "Missing provider should return 404 (got HTTP $HTTP_CODE)"
fi

# Test 14: Unauthorized access
echo ""
echo "Test 14: Unauthorized access (should fail)"
RESPONSE=$(curl -s $CURL_OPTS -w "\n%{http_code}" "$BASE_URL/v1/mode")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "401" ]; then
    print_result 0 "Unauthorized access correctly rejected"
else
    print_result 1 "Unauthorized access should return 401 (got HTTP $HTTP_CODE)"
fi

echo ""
echo "======================================"
echo -e "${GREEN}All tests passed!${NC}"
echo "======================================"
echo ""
echo "API is ready for use. Example usage:"
echo ""
echo "  # Register device (save the token)"
echo "  curl -X POST $BASE_URL/v1/auth/register -H 'Content-Type: application/json' -d '{\"device_name\": \"my-device\"}'"
echo ""
echo "  # Send message"
echo "  curl -X POST $BASE_URL/v1/chat -H 'Content-Type: application/json' -H 'X-Hestia-Device-Token: YOUR_TOKEN' -d '{\"message\": \"Hello Tia\"}'"
echo ""
