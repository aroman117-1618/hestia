#!/bin/bash
# auto-build-swift.sh
# Post-edit hook: automatically builds the relevant Xcode target(s)
# after a Swift source file is edited.
#
# Usage (CLI):   ./scripts/auto-build-swift.sh <edited_file_path>
# Usage (hook):  Called by Claude Code PostToolUse hook — reads JSON from stdin
#
# Determines which target(s) to build based on file location:
#   - Shared/ files → build both iOS + macOS
#   - macOS/ files  → build macOS only
#   - iOS-only files → build iOS only

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
XCODEPROJ="$PROJECT_ROOT/HestiaApp/HestiaApp.xcodeproj"

# Dual-mode: CLI argument or Claude Code hook stdin JSON
if [ -n "$1" ]; then
    FILE_PATH="$1"
else
    INPUT=$(cat)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
    if [ -z "$FILE_PATH" ]; then
        exit 0
    fi
fi

# Only trigger for Swift files in HestiaApp
case "$FILE_PATH" in
    *HestiaApp/*.swift) ;;
    *) exit 0 ;;
esac

# Determine which targets to build
BUILD_IOS=false
BUILD_MACOS=false

case "$FILE_PATH" in
    *HestiaApp/macOS/*)
        BUILD_MACOS=true
        ;;
    *HestiaApp/Shared/*)
        BUILD_IOS=true
        BUILD_MACOS=true
        ;;
    *)
        # Default: iOS only (covers any iOS-specific files)
        BUILD_IOS=true
        ;;
esac

# Check if xcodeproj exists
if [ ! -d "$XCODEPROJ" ]; then
    echo "[AUTO-BUILD] Xcode project not found: $XCODEPROJ"
    exit 0
fi

FAILED=false
FILENAME=$(basename "$FILE_PATH")

if [ "$BUILD_IOS" = true ]; then
    echo "[AUTO-BUILD] Building iOS (HestiaApp) — triggered by $FILENAME"
    BUILD_LOG=$(mktemp)
    xcodebuild build \
        -project "$XCODEPROJ" \
        -scheme HestiaApp \
        -destination 'generic/platform=iOS' \
        CODE_SIGNING_ALLOWED=NO \
        2>&1 | tail -30 > "$BUILD_LOG"

    if grep -q "BUILD SUCCEEDED" "$BUILD_LOG"; then
        echo "[AUTO-BUILD] iOS: BUILD SUCCEEDED"
    else
        echo "[AUTO-BUILD] iOS: BUILD FAILED"
        grep "error:" "$BUILD_LOG" | head -10
        FAILED=true
    fi
    rm -f "$BUILD_LOG"
fi

if [ "$BUILD_MACOS" = true ]; then
    echo "[AUTO-BUILD] Building macOS (HestiaWorkspace) — triggered by $FILENAME"
    BUILD_LOG=$(mktemp)
    xcodebuild build \
        -project "$XCODEPROJ" \
        -scheme HestiaWorkspace \
        -destination 'platform=macOS' \
        CODE_SIGNING_ALLOWED=NO \
        2>&1 | tail -30 > "$BUILD_LOG"

    if grep -q "BUILD SUCCEEDED" "$BUILD_LOG"; then
        echo "[AUTO-BUILD] macOS: BUILD SUCCEEDED"
    else
        echo "[AUTO-BUILD] macOS: BUILD FAILED"
        grep "error:" "$BUILD_LOG" | head -10
        FAILED=true
    fi
    rm -f "$BUILD_LOG"
fi

if [ "$FAILED" = true ]; then
    echo "[AUTO-BUILD] One or more targets FAILED. Review errors above."
    exit 1
else
    echo "[AUTO-BUILD] All targets passed."
    exit 0
fi
