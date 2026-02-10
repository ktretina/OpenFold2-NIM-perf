#!/bin/bash
set -e

CONFIG=${1:-configs/default.yaml}

# Fix #5: Validate config file exists
if [ ! -f "$CONFIG" ]; then
    echo "ERROR: Config file not found: $CONFIG"
    echo "Usage: $0 [config_file]"
    exit 1
fi

RUN_ID="run_$(date +%Y%m%d_%H%M%S)"

echo "=== Running OpenFold2-NIM Benchmark ==="
echo "Config: $CONFIG"
echo "Run ID: $RUN_ID"

# 1. Preflight checks
echo "Step 1/5: Preflight checks"
bench preflight || { echo "Preflight checks failed"; exit 1; }

# 2. Prepare data
echo "Step 2/5: Preparing dataset"
bench prepare-data --config "$CONFIG"

# 3. Run benchmarks
echo "Step 3/5: Running benchmarks"
bench run --config "$CONFIG" --output-dir "results/$RUN_ID"

# 4. Generate analysis
echo "Step 4/5: Generating analysis"
bench analyze "results/$RUN_ID"

echo "=== Benchmark Complete ==="
echo "Results: results/$RUN_ID/analysis/report.html"

# Fix #6: Improve persistent storage copy safety
if [ -n "$PERSISTENT_VOLUME" ]; then
    PERSISTENT_DIR="$PERSISTENT_VOLUME/openfold_results"
    echo "Copying results to persistent storage: $PERSISTENT_DIR"

    # Create directory with validation
    mkdir -p "$PERSISTENT_DIR" || {
        echo "ERROR: Cannot create persistent directory: $PERSISTENT_DIR"
        echo "Check permissions or PERSISTENT_VOLUME setting"
        exit 1
    }

    # Copy results with validation
    if ! cp -r "results/$RUN_ID" "$PERSISTENT_DIR/"; then
        echo "ERROR: Failed to copy results to persistent storage"
        echo "Source: results/$RUN_ID"
        echo "Destination: $PERSISTENT_DIR/"
        exit 1
    fi

    echo "✓ Persistent copy successful: $PERSISTENT_DIR/$RUN_ID"
fi
