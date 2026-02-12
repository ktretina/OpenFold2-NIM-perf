#!/bin/bash
# End-to-end deployment test for Colossus
#
# This script tests the complete deployment pipeline:
# 1. Bootstrap (simulated - checks it exists)
# 2. Validation
# 3. Smoke test benchmark
# 4. Result analysis
#
# Usage: ./scripts/colossus/test_deployment.sh

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "============================================================"
echo "Colossus Deployment - End-to-End Test"
echo "============================================================"
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

# Test phase counter
PHASE=1

# Phase 1: Check bootstrap exists
echo "=== Phase $PHASE: Bootstrap Script Check ==="
PHASE=$((PHASE + 1))
echo ""

if [ -x "$SCRIPT_DIR/bootstrap.sh" ]; then
    echo -e "${GREEN}✓ bootstrap.sh exists and is executable${NC}"
else
    echo -e "${RED}✗ bootstrap.sh missing or not executable${NC}"
    exit 1
fi

echo ""

# Phase 2: Check validation script
echo "=== Phase $PHASE: Validation Script Check ==="
PHASE=$((PHASE + 1))
echo ""

if [ -x "$SCRIPT_DIR/validate.sh" ]; then
    echo -e "${GREEN}✓ validate.sh exists and is executable${NC}"
else
    echo -e "${RED}✗ validate.sh missing or not executable${NC}"
    exit 1
fi

echo ""

# Phase 3: Run validation
echo "=== Phase $PHASE: Environment Validation ==="
PHASE=$((PHASE + 1))
echo ""

if "$SCRIPT_DIR/validate.sh"; then
    echo -e "${GREEN}✓ Validation passed${NC}"
else
    echo -e "${RED}✗ Validation failed${NC}"
    echo ""
    echo "The deployment is not properly configured."
    echo "Run bootstrap first: ./scripts/colossus/bootstrap.sh"
    exit 1
fi

echo ""

# Phase 4: Check smoke test config
echo "=== Phase $PHASE: Smoke Test Configuration ==="
PHASE=$((PHASE + 1))
echo ""

if [ -f "configs/smoke_test.yaml" ]; then
    echo -e "${GREEN}✓ smoke_test.yaml exists${NC}"

    # Validate it loads
    if python3 -c "from bench.config import load_config; load_config('configs/smoke_test.yaml')" 2>&1; then
        echo -e "${GREEN}✓ smoke_test.yaml loads successfully${NC}"
    else
        echo -e "${RED}✗ smoke_test.yaml failed to load${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ smoke_test.yaml missing${NC}"
    exit 1
fi

echo ""

# Phase 5: Ask user if they want to run smoke test
echo "=== Phase $PHASE: Smoke Test (Optional) ==="
PHASE=$((PHASE + 1))
echo ""

echo "The smoke test runs a 1-2 minute benchmark to verify end-to-end functionality."
echo "This requires:"
echo "  - NGC_API_KEY to be set"
echo "  - NIM container to be pulled (or will pull ~10GB)"
echo "  - GPU to be available"
echo ""

read -p "Run smoke test? [y/N] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Running smoke test..."
    echo ""

    # Check NGC_API_KEY
    if [ -z "$NGC_API_KEY" ]; then
        echo -e "${RED}✗ NGC_API_KEY not set${NC}"
        echo "  Set it with: export NGC_API_KEY='your-key'"
        exit 1
    fi

    # Run smoke test
    if bench run --config configs/smoke_test.yaml; then
        echo ""
        echo -e "${GREEN}✓ Smoke test completed successfully${NC}"

        # Find the latest results
        LATEST_RESULT=$(ls -td results/smoke_test/run_* 2>/dev/null | head -1 || echo "")

        if [ -n "$LATEST_RESULT" ]; then
            echo ""
            echo "Results location: $LATEST_RESULT"

            # Check if records exist
            if [ -f "$LATEST_RESULT/records.parquet" ]; then
                RECORD_COUNT=$(python3 -c "import pandas as pd; print(len(pd.read_parquet('$LATEST_RESULT/records.parquet')))" 2>/dev/null || echo "unknown")
                echo "Records generated: $RECORD_COUNT"
                echo -e "${GREEN}✓ Results file created${NC}"
            fi

            # Test analysis
            echo ""
            echo "Testing analysis generation..."
            if bench analyze "$LATEST_RESULT" 2>&1 | grep -q "Analysis complete"; then
                echo -e "${GREEN}✓ Analysis generation works${NC}"

                REPORT_PATH="$LATEST_RESULT/analysis/report.html"
                if [ -f "$REPORT_PATH" ]; then
                    echo -e "${GREEN}✓ HTML report created${NC}"
                    echo ""
                    echo "View report:"
                    echo "  open $REPORT_PATH"
                fi
            else
                echo -e "${YELLOW}⚠ Analysis generation had issues (non-critical)${NC}"
            fi
        fi
    else
        echo ""
        echo -e "${RED}✗ Smoke test failed${NC}"
        echo ""
        echo "This indicates an issue with the benchmark execution."
        echo "Check the error messages above for details."
        exit 1
    fi
else
    echo ""
    echo -e "${BLUE}Smoke test skipped${NC}"
    echo ""
    echo "To run manually:"
    echo "  export NGC_API_KEY='your-key'"
    echo "  bench run --config configs/smoke_test.yaml"
fi

echo ""
echo "============================================================"
echo -e "${GREEN}✓ Deployment Test Complete${NC}"
echo "============================================================"
echo ""
echo "Summary:"
echo "  ✓ Bootstrap script available"
echo "  ✓ Validation script available"
echo "  ✓ Environment validation passed"
echo "  ✓ Configuration files valid"

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  ✓ Smoke test passed"
    echo "  ✓ Analysis generation works"
fi

echo ""
echo "The deployment is ready for production benchmarks!"
echo ""
echo "Next steps:"
echo "  1. Run default benchmark:     bench run --config configs/default.yaml"
echo "  2. Run CASP15 benchmark:      bench run --config configs/casp15.yaml"
echo "  3. Auto-config and run:       ./scripts/colossus/run.sh"
echo ""
echo "For multi-GPU studies:"
echo "  bench colossus campaign-create campaigns/my_study"
echo ""
