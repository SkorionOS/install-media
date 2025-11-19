#!/bin/bash
# Test script for installer retry mechanism
# This simulates the behavior of install-init.sh and installer-modular

set +e  # Allow failures for testing

echo "=========================================="
echo "Installer Retry Mechanism Test"
echo "=========================================="
echo ""

# ===== Configuration =====
FAILURE_TRACKER="/tmp/test-installer-failures"
MIN_RUN_DURATION=15
MAX_FAILURES=2
TEST_MODE="${1:-always_fail}"  # Test modes: always_fail, fail_twice, timeout_once, crash_once, success, text_installer_fail
TEXT_INSTALLER_SHOULD_FAIL=false

# Clean up from previous tests
rm -f "$FAILURE_TRACKER" /tmp/installer_success /tmp/installer_started /tmp/test-installer.log

# ===== Mock text installer (install.sh) =====
mock_text_installer() {
    echo ""
    echo "=========================================="
    echo "Mock Text Installer (install.sh)"
    echo "=========================================="
    echo ""
    
    if [ "$TEXT_INSTALLER_SHOULD_FAIL" = true ]; then
        echo "Starting text-based installation..."
        sleep 1
        echo "✓ Disk selection"
        sleep 1
        echo "❌ Installation failed: disk error"
        echo ""
        echo "Text installer failed"
        return 1
    else
        echo "Starting text-based installation..."
        sleep 2
        echo "✓ Disk selection"
        sleep 1
        echo "✓ Timezone configuration"
        sleep 1
        echo "✓ Network configuration"
        sleep 1
        echo "✓ Installation completed"
        echo ""
        echo "Text installer finished successfully"
        return 0
    fi
}

# ===== Mock installer-modular =====
mock_installer_modular() {
    local run_number=$1
    local start_time=$SECONDS
    
    echo ""
    echo "=========================================="
    echo "Mock installer-modular - Run #$run_number"
    echo "Test mode: $TEST_MODE"
    echo "=========================================="
    echo ""
    
    # Simulate different failure scenarios based on test mode
    case "$TEST_MODE" in
        "always_fail")
            echo "Simulating: Socket timeout (gamescope startup failure)"
            sleep 2  # Quick failure
            return 1
            ;;
            
        "fail_twice")
            if [ $run_number -le 2 ]; then
                echo "Simulating: Socket timeout on attempt $run_number"
                sleep 2
                return 1
            else
                echo "Simulating: Success on attempt $run_number"
                touch /tmp/installer_started
                sleep 5
                touch /tmp/installer_success
                return 0
            fi
            ;;
            
        "timeout_once")
            if [ $run_number -eq 1 ]; then
                echo "Simulating: Socket timeout on first attempt"
                sleep 2
                return 1
            else
                echo "Simulating: Success on attempt $run_number"
                touch /tmp/installer_started
                sleep 5
                touch /tmp/installer_success
                return 0
            fi
            ;;
            
        "crash_once")
            if [ $run_number -eq 1 ]; then
                echo "Simulating: Python crash (started but crashed)"
                touch /tmp/installer_started
                sleep 8  # Run for a bit then crash
                # Don't create installer_success
                return 1
            else
                echo "Simulating: Success on attempt $run_number"
                touch /tmp/installer_started
                sleep 5
                touch /tmp/installer_success
                return 0
            fi
            ;;
            
        "success")
            echo "Simulating: Immediate success"
            touch /tmp/installer_started
            sleep 5
            touch /tmp/installer_success
            return 0
            ;;
            
        "text_installer_fail")
            echo "Simulating: Graphical installer fails, text installer will also fail"
            sleep 2
            return 1
            ;;
            
        *)
            echo "Unknown test mode: $TEST_MODE"
            return 1
            ;;
    esac
}

# ===== Main retry logic (from install-init.sh) =====
main_retry_loop() {
    local attempt=1
    
    while true; do
        echo ""
        echo "╔════════════════════════════════════════╗"
        echo "║  Attempt $attempt/$((MAX_FAILURES + 1))"
        echo "╚════════════════════════════════════════╝"
        
        # Check failure count before attempt
        failure_count=0
        [ -f "$FAILURE_TRACKER" ] && failure_count=$(wc -l < "$FAILURE_TRACKER")
        
        # Check if we should give up
        if [ "$failure_count" -ge "$MAX_FAILURES" ]; then
            echo ""
            echo "=========================================="
            echo "❌ Maximum failures reached ($MAX_FAILURES)"
            echo "=========================================="
            echo "Falling back to text installer..."
            sleep 1
            
            # Clean up failure tracker before fallback
            rm -f "$FAILURE_TRACKER"
            
            # Run text installer
            if mock_text_installer; then
                echo ""
                echo "✅ Text installer succeeded as fallback"
                return 0
            else
                echo ""
                echo "❌ Text installer also failed"
                return 1
            fi
        fi
        
        # Clean up state files
        rm -f /tmp/installer_success /tmp/installer_started
        
        # Run mock installer
        START_TIME=$SECONDS
        mock_installer_modular $attempt
        EXIT_CODE=$?
        RUN_DURATION=$((SECONDS - START_TIME))
        
        echo ""
        echo "Exit code: $EXIT_CODE"
        echo "Run duration: ${RUN_DURATION}s"
        
        # ===== Failure Detection Logic =====
        IS_FAILURE=false
        FAILURE_REASON=""
        
        # Check 1: State file detection
        if [ -f /tmp/installer_started ]; then
            echo "✓ installer_started exists"
            if [ ! -f /tmp/installer_success ]; then
                IS_FAILURE=true
                FAILURE_REASON="Started but crashed/abnormal exit"
            else
                echo "✓ installer_success exists"
            fi
        else
            echo "✗ installer_started NOT found"
            if [ "$EXIT_CODE" -ne 0 ]; then
                IS_FAILURE=true
                FAILURE_REASON="Socket timeout or gamescope crash"
            fi
        fi
        
        # Check 2: Quick exit detection
        if [ "$IS_FAILURE" = false ] && [ "$RUN_DURATION" -lt "$MIN_RUN_DURATION" ] && [ "$EXIT_CODE" -ne 0 ]; then
            IS_FAILURE=true
            FAILURE_REASON="Quick abnormal exit (${RUN_DURATION}s < ${MIN_RUN_DURATION}s)"
        fi
        
        # ===== Handle result =====
        if [ "$IS_FAILURE" = true ]; then
            echo ""
            echo "┌────────────────────────────────────────┐"
            echo "│ ❌ FAILURE DETECTED"
            echo "│ Reason: $FAILURE_REASON"
            echo "└────────────────────────────────────────┘"
            
            # Record failure
            echo "failure at $(date)" >> "$FAILURE_TRACKER"
            new_count=$(wc -l < "$FAILURE_TRACKER")
            
            echo "Failure count: ${new_count}/${MAX_FAILURES}"
            
            if [ "$new_count" -ge "$MAX_FAILURES" ]; then
                echo ""
                echo "=========================================="
                echo "Giving up after $new_count failures"
                echo "=========================================="
                echo "Falling back to text installer..."
                sleep 1
                
                # Clean up failure tracker before fallback
                rm -f "$FAILURE_TRACKER"
                
                # Run text installer
                if mock_text_installer; then
                    echo ""
                    echo "✅ Text installer succeeded as fallback"
                    return 0
                else
                    echo ""
                    echo "❌ Text installer also failed"
                    return 1
                fi
            else
                echo "Retrying in 2 seconds..."
                sleep 2
                attempt=$((attempt + 1))
                continue
            fi
        else
            echo ""
            echo "┌────────────────────────────────────────┐"
            echo "│ ✅ SUCCESS"
            echo "└────────────────────────────────────────┘"
            
            # Clear failure tracker
            rm -f "$FAILURE_TRACKER"
            return 0
        fi
    done
}

# ===== Setup test mode =====
if [ "$TEST_MODE" = "text_installer_fail" ]; then
    TEXT_INSTALLER_SHOULD_FAIL=true
fi

# ===== Run test =====
echo "Starting test with mode: $TEST_MODE"
echo ""

if main_retry_loop; then
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║  TEST RESULT: ✅ SUCCESS"
    echo "║  (图形或文本安装器成功完成)"
    echo "╚════════════════════════════════════════╝"
    EXIT_STATUS=0
else
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║  TEST RESULT: ❌ FAILED"
    echo "║  (图形和文本安装器都失败)"
    echo "╚════════════════════════════════════════╝"
    EXIT_STATUS=1
fi

# Cleanup
rm -f "$FAILURE_TRACKER" /tmp/installer_success /tmp/installer_started

echo ""
echo "Test completed"
exit $EXIT_STATUS

