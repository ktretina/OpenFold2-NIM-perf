#!/bin/bash
# One-click entrypoint for running benchmarks on Colossus
#
# This script orchestrates the full benchmark workflow:
# 1. Bootstrap (first-time setup)
# 2. Hardware auto-detection
# 3. Environment validation
# 4. Benchmark execution with checkpointing
#
# Usage:
#   ./scripts/colossus/run.sh [config_file]
#
# Environment variables:
#   AUTO_DETECT       - Enable hardware detection (default: true)
#   CHECKPOINT        - Enable checkpointing (default: true)
#   PUSH_RESULTS      - Enable Git sync (default: false)
#   FAST_WORKDIR      - Override fast storage path
#   PERSIST_DIR       - Override persistent storage path

set -e

# Configuration
CONFIG=${1:-configs/default.yaml}
AUTO_DETECT=${AUTO_DETECT:-true}
CHECKPOINT=${CHECKPOINT:-true}
PUSH_RESULTS=${PUSH_RESULTS:-false}
SKIP_VALIDATION=${SKIP_VALIDATION:-false}

echo "============================================================"
echo "OpenFold2-NIM Benchmark - Colossus One-Click Runner"
echo "============================================================"
echo ""
echo "Configuration:"
echo "  Base config:     $CONFIG"
echo "  Auto-detect:     $AUTO_DETECT"
echo "  Checkpointing:   $CHECKPOINT"
echo "  Git sync:        $PUSH_RESULTS"
echo "  Validation:      $([ "$SKIP_VALIDATION" = "true" ] && echo "disabled" || echo "enabled")"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

# Phase 1: Bootstrap (if needed)
if [ ! -f ".env.colossus" ]; then
    echo "=== Phase 1: Bootstrap (first-time setup) ==="
    echo ""
    if [ -f "$SCRIPT_DIR/bootstrap.sh" ]; then
        bash "$SCRIPT_DIR/bootstrap.sh"
    else
        echo "⚠️  Bootstrap script not found, continuing anyway..."
    fi

    # Source environment if created
    if [ -f ".env.colossus" ]; then
        source .env.colossus
    fi
    echo ""
fi

# Phase 2: Auto-detect hardware and generate config
FINAL_CONFIG="$CONFIG"

if [ "$AUTO_DETECT" = "true" ]; then
    echo "=== Phase 2: Hardware Auto-Detection ==="
    echo ""

    # Detect hardware and display info
    bench colossus detect

    # Generate optimized config
    mkdir -p configs/generated
    GENERATED_CONFIG=$(bench colossus auto-config \
        --base-config "$CONFIG" \
        --output-dir configs/generated 2>&1 | grep "Config generated:" | awk '{print $NF}')

    if [ -n "$GENERATED_CONFIG" ] && [ -f "$GENERATED_CONFIG" ]; then
        FINAL_CONFIG="$GENERATED_CONFIG"
        echo ""
        echo "✓ Using auto-generated config: $FINAL_CONFIG"
    else
        echo "⚠️  Auto-config failed, using base config: $CONFIG"
    fi
    echo ""
fi

# Phase 3: Validation
if [ "$SKIP_VALIDATION" != "true" ]; then
    echo "=== Phase 3: Environment Validation ==="
    echo ""

    # Run comprehensive validation
    if [ -x "$SCRIPT_DIR/validate.sh" ]; then
        "$SCRIPT_DIR/validate.sh" || {
            echo ""
            echo "✗ Validation failed!"
            echo "  Fix the issues above before running the benchmark."
            echo "  To skip validation: SKIP_VALIDATION=true ./scripts/colossus/run.sh"
            exit 1
        }
    else
        # Fallback to basic preflight if validate.sh not available
        bench preflight || {
            echo ""
            echo "✗ Preflight checks failed!"
            echo "  Fix the issues above before running the benchmark."
            exit 1
        }
    fi
    echo ""
else
    echo "=== Phase 3: Validation (skipped) ==="
    echo ""
fi

# Phase 4: Run benchmark
echo "=== Phase 4: Running Benchmark ==="
echo ""
echo "Config: $FINAL_CONFIG"
echo ""

# Build run command
RUN_CMD="bench run --config $FINAL_CONFIG"

# Add verbose flag for better logging
RUN_CMD="$RUN_CMD --verbose"

# Note: Checkpoint and Git sync would be integrated into the orchestrator
# For now, just run the standard benchmark
$RUN_CMD

echo ""
echo "============================================================"
echo "✓ Benchmark Complete!"
echo "============================================================"
echo ""
echo "Results are in the output directory specified in the config."
echo ""
echo "Next steps:"
echo "  1. Analyze results:  bench analyze results/latest"
echo "  2. View reports:     open results/latest/analysis/report.html"
echo ""
