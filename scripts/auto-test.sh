#!/bin/bash
# auto-test.sh
# Post-edit hook: automatically runs the relevant test file
# after a Python source file is edited.
#
# Usage: ./scripts/auto-test.sh <edited_file_path>
# Maps source files to their corresponding test files and runs them.

FILE_PATH="${1}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Only trigger for Python source files in the hestia package
if [[ "$FILE_PATH" != *".py" ]] || [[ "$FILE_PATH" == *"test_"* ]] || [[ "$FILE_PATH" != *"hestia/"* ]]; then
    exit 0  # Not a Python source file or already a test file
fi

# Map source modules to test files
declare -A MODULE_TO_TEST
MODULE_TO_TEST["hestia/inference/"]="tests/test_inference.py"
MODULE_TO_TEST["hestia/memory/"]="tests/test_memory.py"
MODULE_TO_TEST["hestia/orchestration/"]="tests/test_orchestration.py"
MODULE_TO_TEST["hestia/execution/"]="tests/test_execution.py"
MODULE_TO_TEST["hestia/apple/"]="tests/test_apple.py"
MODULE_TO_TEST["hestia/tasks/"]="tests/test_tasks.py"
MODULE_TO_TEST["hestia/orders/"]="tests/test_orders.py"
MODULE_TO_TEST["hestia/agents/"]="tests/test_agents.py"
MODULE_TO_TEST["hestia/user/"]="tests/test_user.py"
MODULE_TO_TEST["hestia/proactive/"]="tests/test_proactive.py"
MODULE_TO_TEST["hestia/api/routes/cloud.py"]="tests/test_cloud_routes.py"
MODULE_TO_TEST["hestia/api/routes/voice.py"]="tests/test_voice_routes.py"
MODULE_TO_TEST["hestia/cloud/"]="tests/test_cloud.py tests/test_cloud_client.py"
MODULE_TO_TEST["hestia/voice/"]="tests/test_voice.py"
MODULE_TO_TEST["hestia/council/"]="tests/test_council.py"
MODULE_TO_TEST["hestia/health/"]="tests/test_health.py"
MODULE_TO_TEST["hestia/api/routes/health_data.py"]="tests/test_health.py"

# Find matching test file
TEST_FILE=""
for module in "${!MODULE_TO_TEST[@]}"; do
    if [[ "$FILE_PATH" == *"$module"* ]]; then
        TEST_FILE="${MODULE_TO_TEST[$module]}"
        break
    fi
done

if [ -z "$TEST_FILE" ]; then
    echo "[AUTO-TEST] No test mapping for: $FILE_PATH"
    exit 0
fi

FULL_TEST_PATH="$PROJECT_ROOT/$TEST_FILE"

if [ ! -f "$FULL_TEST_PATH" ]; then
    echo "[AUTO-TEST] Test file not found: $TEST_FILE"
    exit 0
fi

echo "[AUTO-TEST] Running: $TEST_FILE (triggered by edit to $FILE_PATH)"

cd "$PROJECT_ROOT"
python -m pytest "$TEST_FILE" -v --tb=short -q 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[AUTO-TEST] All tests passed."
else
    echo "[AUTO-TEST] Some tests FAILED. Review output above."
fi

exit $EXIT_CODE
