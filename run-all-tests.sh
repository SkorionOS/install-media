#!/bin/bash
# Run all test scenarios for the retry mechanism

echo "╔════════════════════════════════════════════════════════╗"
echo "║  Installer Retry Mechanism - Test Suite"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

TEST_SCRIPT="./test-retry-mechanism.sh"
RESULTS=()

run_test() {
    local mode="$1"
    local description="$2"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Test: $description"
    echo "Mode: $mode"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if $TEST_SCRIPT "$mode"; then
        RESULTS+=("✅ $description")
        return 0
    else
        RESULTS+=("❌ $description")
        return 1
    fi
}

# Run all test scenarios
run_test "success" "Scenario 1: Immediate success (graphical)"
run_test "timeout_once" "Scenario 2: Timeout once, then success"
run_test "crash_once" "Scenario 3: Crash once, then success"
run_test "always_fail" "Scenario 4: Graphical fails, fallback to text (success)"
run_test "text_installer_fail" "Scenario 5: Both graphical and text fail"

# Summary
echo ""
echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  TEST SUMMARY"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

for result in "${RESULTS[@]}"; do
    echo "$result"
done

echo ""
echo "Total tests: ${#RESULTS[@]}"
echo ""

