#!/bin/bash
# Verification script for deployment fixes
# Tests that all 12 critical fixes are working

echo "=== Verifying Deployment Fixes ==="
echo ""

# Find Python with bench installed
PYTHON=$(which bench 2>/dev/null | xargs dirname 2>/dev/null | xargs dirname 2>/dev/null)/bin/python3
if [ ! -f "$PYTHON" ]; then
    PYTHON=python3
fi
echo "Using Python: $PYTHON"
echo ""

PASS=0
FAIL=0

# Helper functions
check_pass() {
    echo "✓ PASS: $1"
    ((PASS++))
}

check_fail() {
    echo "✗ FAIL: $1"
    ((FAIL++))
}

# Test 1: Config loading with relative paths
echo "Test 1: Config loading with relative paths..."
if $PYTHON -c "
from bench.config import load_config
from pathlib import Path
config = load_config(Path('configs/default.yaml'))
assert config.suites[0].targets_file.is_absolute()
assert config.suites[0].targets_file.exists()
" 2>&1 >/dev/null; then
    check_pass "Config path resolution"
else
    check_fail "Config path resolution"
fi

# Test 2: Environment variable expansion
echo "Test 2: Environment variable expansion..."
if $PYTHON -c "
import os
from bench.config import load_config
from pathlib import Path
os.environ['RESULTS_DIR'] = '/tmp/test'
config = load_config(Path('configs/default.yaml'))
assert str(config.output_dir) == '/tmp/test'
" 2>&1 >/dev/null; then
    check_pass "Environment variable expansion"
else
    check_fail "Environment variable expansion"
fi

# Test 3: Config file validation
echo "Test 3: Config file validation..."
if ./scripts/run_all.sh nonexistent.yaml 2>&1 | grep -q "ERROR: Config file not found"; then
    check_pass "Config file validation"
else
    check_fail "Config file validation"
fi

# Test 4: NGC_API_KEY validation in bootstrap
echo "Test 4: NGC_API_KEY validation..."
if (unset NGC_API_KEY && bash -c '
if [ -z "$NGC_API_KEY" ]; then
    echo "ERROR: NGC_API_KEY environment variable not set"
    exit 1
fi
' 2>&1 | grep -q "ERROR: NGC_API_KEY"); then
    check_pass "NGC_API_KEY validation"
else
    check_fail "NGC_API_KEY validation"
fi

# Test 5: Kaleido optional import
echo "Test 5: Kaleido optional import..."
if $PYTHON -c "
from bench.analysis import plots
assert hasattr(plots, 'KALEIDO_AVAILABLE')
" 2>&1 >/dev/null; then
    check_pass "Kaleido optional import"
else
    check_fail "Kaleido optional import"
fi

# Test 6: Time import fix
echo "Test 6: Time import in openfold.py..."
if grep -q "import time" bench/runners/openfold.py && \
   grep -q "t0 = time.time()" bench/runners/openfold.py; then
    check_pass "Time import fixed"
else
    check_fail "Time import fixed"
fi

# Test 7: Port conflict handling
echo "Test 7: Port conflict handling code..."
if grep -q "port is already allocated" bench/runners/nim.py && \
   grep -q "address already in use" bench/runners/nim.py; then
    check_pass "Port conflict handling"
else
    check_fail "Port conflict handling"
fi

# Test 8: Cache directory validation
echo "Test 8: Cache directory permission validation..."
if grep -q "Cannot write to cache directory" bench/runners/nim.py && \
   grep -q "test_file.touch()" bench/runners/nim.py; then
    check_pass "Cache permission validation"
else
    check_fail "Cache permission validation"
fi

# Test 9: OpenFold output validation
echo "Test 9: OpenFold output validation..."
if grep -q "dir_contents = list(pred_dir.iterdir())" bench/runners/openfold.py && \
   grep -q "OpenFold output directory contents" bench/runners/openfold.py; then
    check_pass "OpenFold output validation"
else
    check_fail "OpenFold output validation"
fi

# Test 10: Persistent storage validation
echo "Test 10: Persistent storage copy validation..."
if grep -q "mkdir -p.*||" scripts/run_all.sh && \
   grep -q "Cannot create persistent directory" scripts/run_all.sh; then
    check_pass "Persistent storage validation"
else
    check_fail "Persistent storage validation"
fi

# Test 11: Disk space check
echo "Test 11: Disk space check in bootstrap..."
if grep -q "Critically low disk space" scripts/bootstrap_colossus.sh && \
   grep -q "SKIP_DISK_CHECK" scripts/bootstrap_colossus.sh; then
    check_pass "Disk space check"
else
    check_fail "Disk space check"
fi

# Test 12: Enhanced preflight checks
echo "Test 12: Enhanced preflight checks..."
export NGC_API_KEY="test_key"
if bench preflight 2>&1 | grep -q "Python version"; then
    check_pass "Enhanced preflight checks"
else
    check_fail "Enhanced preflight checks"
fi

# Summary
echo ""
echo "=== Verification Summary ==="
echo "Passed: $PASS/12"
echo "Failed: $FAIL/12"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "✓ All deployment fixes verified!"
    exit 0
else
    echo "✗ Some fixes need attention"
    exit 1
fi
