#!/bin/bash
set -e

CONFIG=${1:-configs/default.yaml}
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

# Copy to persistent storage if on Colossus
if [ -n "$PERSISTENT_VOLUME" ]; then
    echo "Copying results to persistent storage..."
    cp -r "results/$RUN_ID" "$PERSISTENT_VOLUME/openfold_results/"
    echo "Persistent copy: $PERSISTENT_VOLUME/openfold_results/$RUN_ID"
fi
