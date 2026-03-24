#!/bin/bash
# auto-test.sh
# Post-edit hook: automatically runs the relevant test file
# after a Python source file is edited.
#
# Usage (CLI):   ./scripts/auto-test.sh <edited_file_path>
# Usage (hook):  Called by Claude Code PostToolUse hook — reads JSON from stdin
#
# Maps source files to their corresponding test files and runs them.
# Uses case statement (not associative arrays) for macOS bash 3.2 compatibility.
# Wraps pytest in run_with_timeout to prevent ChromaDB thread hangs.

# Kill a process after N seconds (same pattern as pre-push.sh)
run_with_timeout() {
    local secs=$1; shift
    "$@" &
    local pid=$!
    ( sleep "$secs" && kill "$pid" 2>/dev/null ) &
    local watchdog=$!
    wait "$pid" 2>/dev/null
    local exit_code=$?
    kill "$watchdog" 2>/dev/null
    wait "$watchdog" 2>/dev/null
    return $exit_code
}

# Dual-mode: CLI argument or Claude Code hook stdin JSON
if [ -n "$1" ]; then
    FILE_PATH="$1"
else
    # Claude Code hook mode: read JSON from stdin, extract file_path
    INPUT=$(cat)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
    if [ -z "$FILE_PATH" ]; then
        exit 0  # No file path available
    fi
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Only trigger for Python source files in the hestia package
case "$FILE_PATH" in
    *test_*) exit 0 ;;  # Skip test files
    *hestia/*.py) ;;     # Continue for hestia Python source files
    *.py) exit 0 ;;      # Skip non-hestia Python files
    *) exit 0 ;;         # Skip non-Python files
esac

# Map source modules to test files (most specific first)
get_test_file() {
    local fp="$1"
    case "$fp" in
        # User profile (specific paths before broad hestia/user/)
        *hestia/user/config*|*hestia/user/templates*)
            echo "tests/test_user_profile.py" ;;
        *hestia/api/routes/user_profile*)
            echo "tests/test_user_profile.py" ;;
        *hestia/user/*)
            echo "tests/test_user.py" ;;

        # API routes (specific before broad module)
        *hestia/api/routes/cloud*)
            echo "tests/test_cloud_routes.py" ;;
        *hestia/api/routes/voice*)
            echo "tests/test_voice_routes.py" ;;
        *hestia/api/routes/health_data*)
            echo "tests/test_health.py" ;;
        *hestia/api/routes/wiki*)
            echo "tests/test_wiki.py" ;;
        *hestia/api/routes/explorer*)
            echo "tests/test_explorer.py" ;;
        *hestia/api/routes/newsfeed*)
            echo "tests/test_newsfeed.py" ;;
        *hestia/api/routes/investigate*)
            echo "tests/test_investigate.py" ;;
        *hestia/api/routes/health*)
            echo "tests/test_server_lifecycle.py" ;;
        *hestia/api/routes/auth*)
            echo "tests/test_auth_invite.py" ;;
        *hestia/api/middleware/auth*)
            echo "tests/test_auth_invite.py" ;;
        *hestia/api/invite_store*)
            echo "tests/test_auth_invite.py" ;;

        # Server lifecycle
        *hestia/api/server*)
            echo "tests/test_server_lifecycle.py" ;;

        # Base database (shared by all modules)
        *hestia/database*)
            echo "tests/test_server_lifecycle.py" ;;

        # Backend modules
        *hestia/inference/*)
            echo "tests/test_inference.py" ;;
        *hestia/memory/database*)
            echo "tests/test_memory.py tests/test_server_lifecycle.py" ;;
        *hestia/memory/*)
            echo "tests/test_memory.py" ;;
        *hestia/orchestration/handler*)
            echo "tests/test_orchestration.py tests/test_session_ttl.py" ;;
        *hestia/orchestration/*)
            echo "tests/test_orchestration.py" ;;
        *hestia/execution/*)
            echo "tests/test_execution.py" ;;
        *hestia/apple/*)
            echo "tests/test_apple.py" ;;
        *hestia/tasks/*)
            echo "tests/test_tasks.py" ;;
        *hestia/orders/*)
            echo "tests/test_orders.py" ;;
        *hestia/agents/*)
            echo "tests/test_agents.py" ;;
        *hestia/proactive/*)
            echo "tests/test_proactive.py" ;;
        *hestia/cloud/*)
            echo "tests/test_cloud.py tests/test_cloud_client.py" ;;
        *hestia/voice/*)
            echo "tests/test_voice.py" ;;
        *hestia/council/*)
            echo "tests/test_council.py" ;;
        *hestia/health/*)
            echo "tests/test_health.py" ;;
        *hestia/wiki/*)
            echo "tests/test_wiki.py" ;;
        *hestia/explorer/*)
            echo "tests/test_explorer.py" ;;
        *hestia/newsfeed/*)
            echo "tests/test_newsfeed.py" ;;
        *hestia/investigate/*)
            echo "tests/test_investigate.py" ;;
        *hestia/research/*)
            echo "tests/test_research.py tests/test_research_facts.py tests/test_research_graph_facts.py" ;;
        *hestia/files/*)
            echo "tests/test_files.py" ;;
        *hestia/api/routes/files*)
            echo "tests/test_files.py" ;;
        *hestia/inbox/*)
            echo "tests/test_inbox.py" ;;
        *hestia/api/routes/inbox*)
            echo "tests/test_inbox.py" ;;
        *hestia/outcomes/*)
            echo "tests/test_outcomes.py" ;;
        *hestia/api/routes/outcomes*)
            echo "tests/test_outcomes.py" ;;
        *hestia/apple_cache/*)
            echo "tests/test_apple_cache.py" ;;
        *hestia/learning/*)
            echo "tests/test_learning_meta_monitor.py tests/test_learning_database.py" ;;
        *hestia/api/routes/learning*)
            echo "tests/test_learning_routes.py" ;;
        *hestia/notifications/*)
            echo "tests/test_notifications.py" ;;
        *hestia/api/routes/notifications*)
            echo "tests/test_notifications.py" ;;
        *hestia/trading/strategies/*|*hestia/trading/data/*)
            echo "tests/test_trading_strategies.py tests/test_trading_indicators.py" ;;
        *hestia/trading/*)
            echo "tests/test_trading_models.py tests/test_trading_database.py tests/test_trading_risk.py tests/test_trading_adapter.py" ;;
        *hestia/api/routes/trading*|*hestia/api/schemas/trading*)
            echo "tests/test_trading_models.py tests/test_trading_database.py tests/test_trading_risk.py tests/test_trading_adapter.py" ;;
        *hestia/workflows/*)
            echo "tests/test_workflow_adapter.py tests/test_workflow_models.py tests/test_workflow_database.py tests/test_workflow_executor.py tests/test_workflow_manager.py tests/test_workflow_routes.py" ;;

        # No mapping found
        *)
            echo "" ;;
    esac
}

TEST_FILE=$(get_test_file "$FILE_PATH")

if [ -z "$TEST_FILE" ]; then
    echo "[AUTO-TEST] No test mapping for: $FILE_PATH"
    exit 0
fi

# Verify test file(s) exist
FIRST_TEST=$(echo "$TEST_FILE" | awk '{print $1}')
FULL_TEST_PATH="$PROJECT_ROOT/$FIRST_TEST"

if [ ! -f "$FULL_TEST_PATH" ]; then
    echo "[AUTO-TEST] Test file not found: $FIRST_TEST"
    exit 0
fi

echo "[AUTO-TEST] Running: $TEST_FILE (triggered by edit to $FILE_PATH)"

cd "$PROJECT_ROOT"

# Use venv python if available, fall back to system python
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
    PYTHON="python3"
fi

PYTEST_LOG=$(mktemp)
run_with_timeout 90 $PYTHON -m pytest $TEST_FILE -v --tb=short -q --timeout=30 >"$PYTEST_LOG" 2>&1
EXIT_CODE=$?

cat "$PYTEST_LOG"

# Exit 143 = killed by timeout. Check if tests actually passed before dying.
if [ $EXIT_CODE -eq 143 ] && grep -q "passed" "$PYTEST_LOG" && ! grep -q "failed" "$PYTEST_LOG"; then
    echo "[AUTO-TEST] All tests passed. (process hung after completion — killed by timeout)"
    rm -f "$PYTEST_LOG"
    exit 0
fi

rm -f "$PYTEST_LOG"

if [ $EXIT_CODE -eq 0 ]; then
    echo "[AUTO-TEST] All tests passed."
else
    echo "[AUTO-TEST] Some tests FAILED. Review output above."
fi

exit $EXIT_CODE
