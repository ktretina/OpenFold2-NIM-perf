#!/bin/bash
# Validation script for Colossus deployment
#
# This script validates that the environment is properly set up
# and all components are working before running benchmarks.

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================================"
echo "Colossus Deployment Validation"
echo "============================================================"
echo ""

TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNED=0

# Test function
run_test() {
    local test_name="$1"
    local test_cmd="$2"
    local is_critical="$3"  # "critical" or "warning"

    echo -n "Testing $test_name... "

    if eval "$test_cmd" &> /tmp/test_output.log; then
        echo -e "${GREEN}✓ PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        if [ "$is_critical" = "critical" ]; then
            echo -e "${RED}✗ FAIL${NC}"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            cat /tmp/test_output.log | head -5
            return 1
        else
            echo -e "${YELLOW}⚠ WARN${NC}"
            TESTS_WARNED=$((TESTS_WARNED + 1))
            return 0
        fi
    fi
}

echo "=== Phase 1: System Requirements ==="
echo ""

run_test "NVIDIA drivers" "nvidia-smi" "critical"
run_test "Docker installed" "docker --version" "critical"
run_test "Docker daemon" "docker ps" "critical"
run_test "Python 3.10+" "python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'" "critical"

echo ""
echo "=== Phase 2: Environment Variables ==="
echo ""

run_test "NGC_API_KEY set" "[ -n \"\$NGC_API_KEY\" ]" "critical"
run_test "FAST_WORKDIR set" "[ -n \"\$FAST_WORKDIR\" ]" "warning"
run_test "PERSIST_DIR set" "[ -n \"\$PERSIST_DIR\" ]" "warning"

echo ""
echo "=== Phase 3: Python Dependencies ==="
echo ""

run_test "pydantic" "python3 -c 'import pydantic'" "critical"
run_test "typer" "python3 -c 'import typer'" "critical"
run_test "pandas" "python3 -c 'import pandas'" "critical"
run_test "numpy" "python3 -c 'import numpy'" "critical"
run_test "docker-py" "python3 -c 'import docker'" "critical"
run_test "py3nvml" "python3 -c 'import py3nvml'" "warning"
run_test "plotly" "python3 -c 'import plotly'" "warning"

echo ""
echo "=== Phase 4: Benchmark Package ==="
echo ""

run_test "bench CLI" "command -v bench" "critical"
run_test "bench.config" "python3 -c 'from bench.config import load_config'" "critical"
run_test "bench.orchestrator" "python3 -c 'from bench.orchestrator import BenchmarkOrchestrator'" "critical"
run_test "bench.colossus" "python3 -c 'from bench.colossus import detect_hardware'" "critical"

echo ""
echo "=== Phase 5: Colossus Modules ==="
echo ""

run_test "checkpoint module" "python3 -c 'from bench.colossus.checkpoint import CheckpointManager'" "critical"
run_test "hardware_detect module" "python3 -c 'from bench.colossus.hardware_detect import detect_hardware'" "critical"
run_test "auto_config module" "python3 -c 'from bench.colossus.auto_config import generate_config'" "critical"
run_test "campaign module" "python3 -c 'from bench.colossus.campaign import Campaign'" "critical"

echo ""
echo "=== Phase 6: Configuration Files ==="
echo ""

run_test "default.yaml exists" "[ -f configs/default.yaml ]" "critical"
run_test "casp15.yaml exists" "[ -f configs/casp15.yaml ]" "warning"
run_test "Config loads" "python3 -c 'from bench.config import load_config; load_config(\"configs/default.yaml\")'" "critical"

echo ""
echo "=== Phase 7: Colossus Scripts ==="
echo ""

run_test "run.sh exists" "[ -x scripts/colossus/run.sh ]" "critical"
run_test "bootstrap.sh exists" "[ -x scripts/colossus/bootstrap.sh ]" "critical"
run_test "pin_versions.sh exists" "[ -x scripts/colossus/pin_versions.sh ]" "warning"

echo ""
echo "=== Phase 8: Hardware Detection ==="
echo ""

echo "Running hardware detection test..."
if python3 -c "
from bench.colossus.hardware_detect import detect_hardware
hw = detect_hardware()
print(f'  GPU: {hw.gpu_model} ({hw.gpu_vram_gb}GB)')
print(f'  Fast storage: {hw.fast_storage_paths[0]}')
print(f'  Recommended warmup: {hw.recommended_warmup}')
print(f'  Recommended measurement: {hw.recommended_measurement}')
" 2>&1; then
    echo -e "${GREEN}✓ Hardware detection works${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}✗ Hardware detection failed${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "=== Phase 9: Preflight Checks ==="
echo ""

if bench preflight 2>&1 | grep -q "All checks passed"; then
    echo -e "${GREEN}✓ Preflight checks pass${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠ Some preflight checks failed (non-critical)${NC}"
    TESTS_WARNED=$((TESTS_WARNED + 1))
fi

echo ""
echo "============================================================"
echo "Validation Results"
echo "============================================================"
echo ""
echo -e "Passed:  ${GREEN}$TESTS_PASSED${NC}"
echo -e "Warned:  ${YELLOW}$TESTS_WARNED${NC}"
echo -e "Failed:  ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo ""
    echo "System is ready for benchmarking."
    echo ""
    echo "Next steps:"
    echo "  1. Generate optimized config: bench colossus auto-config"
    echo "  2. Run benchmark:             ./scripts/colossus/run.sh"
    echo ""
    exit 0
else
    echo -e "${RED}✗ $TESTS_FAILED critical test(s) failed${NC}"
    echo ""
    echo "Fix the issues above before running benchmarks."
    echo "See logs in /tmp/test_output.log for details."
    echo ""
    exit 1
fi
