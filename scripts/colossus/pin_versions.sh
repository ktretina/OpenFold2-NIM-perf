#!/bin/bash
# Helper script to pin versions for reproducibility
#
# This script captures:
# - NIM container digest
# - OpenFold git commit
# - Python dependencies
#
# Usage:
#   ./scripts/colossus/pin_versions.sh [output_file]

set -e

OUTPUT_FILE=${1:-version_pins.yaml}

echo "============================================================"
echo "Version Pinning Helper"
echo "============================================================"
echo ""

# Get NIM container digest
echo "Fetching NIM container digest..."
docker pull nvcr.io/nim/openfold/openfold2:latest > /dev/null 2>&1 || {
    echo "⚠️  Failed to pull NIM container"
    NIM_DIGEST="<unavailable>"
}

if [ "$NIM_DIGEST" != "<unavailable>" ]; then
    NIM_DIGEST=$(docker inspect nvcr.io/nim/openfold/openfold2:latest 2>/dev/null | \
        jq -r '.[0].RepoDigests[0]' 2>/dev/null | \
        cut -d'@' -f2 || echo "<unavailable>")
fi

echo "  NIM digest: $NIM_DIGEST"

# Get OpenFold commit
echo ""
echo "Fetching OpenFold commit hash..."
OPENFOLD_COMMIT=$(git ls-remote https://github.com/aqlaboratory/openfold.git HEAD 2>/dev/null | \
    cut -f1 || echo "<unavailable>")

echo "  OpenFold commit: $OPENFOLD_COMMIT"

# Get benchmark code commit (if in git repo)
echo ""
echo "Fetching benchmark code commit..."
if git rev-parse --git-dir > /dev/null 2>&1; then
    BENCH_COMMIT=$(git rev-parse HEAD)
    echo "  Benchmark commit: $BENCH_COMMIT"
else
    BENCH_COMMIT="<not-in-git>"
    echo "  Benchmark commit: (not in git repository)"
fi

# Freeze Python dependencies
echo ""
echo "Freezing Python dependencies..."
if command -v pip &> /dev/null; then
    pip freeze > requirements.lock
    echo "  Saved to: requirements.lock"
else
    echo "  ⚠️  pip not available, skipping"
fi

# Generate version pins YAML
echo ""
echo "Generating version pins file: $OUTPUT_FILE"

cat > "$OUTPUT_FILE" << EOF
# Version pins for reproducibility
# Generated on $(date)

nim:
  container_image: "nvcr.io/nim/openfold/openfold2:latest"
  container_registry_digest: "$NIM_DIGEST"
  warn_on_latest_tag: false  # Digest pinned

openfold:
  commit_hash: "$OPENFOLD_COMMIT"

benchmark:
  code_commit: "$BENCH_COMMIT"
  python_requirements: "requirements.lock"
EOF

echo ""
echo "============================================================"
echo "✓ Version Pins Saved"
echo "============================================================"
echo ""
echo "Version Information:"
echo "  NIM:         $NIM_DIGEST"
echo "  OpenFold:    $OPENFOLD_COMMIT"
echo "  Benchmark:   $BENCH_COMMIT"
echo ""
echo "Copy these pins into your config file for reproducibility."
echo ""
