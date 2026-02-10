#!/bin/bash
set -e

echo "=== OpenFold2-NIM Benchmark Bootstrap ==="

# 1. Verify prerequisites
echo "Checking prerequisites..."

# Check nvidia-smi
if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: nvidia-smi not found. GPU drivers not installed?"
    exit 1
fi

# Check docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: docker not found. Install Docker."
    exit 1
fi

# Check nvidia-container-toolkit
echo "Testing Docker GPU access..."
if ! docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu20.04 nvidia-smi &> /dev/null; then
    echo "ERROR: nvidia-container-toolkit not working"
    echo "Install with: distribution=$(. /etc/os-release;echo \$ID\$VERSION_ID) && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add - && curl -s -L https://nvidia.github.io/nvidia-docker/\$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list && sudo apt-get update && sudo apt-get install -y nvidia-docker2 && sudo systemctl restart docker"
    exit 1
fi

# Check NGC_API_KEY if running NIM (Fix #2: Make this a blocker)
if [ -z "$NGC_API_KEY" ]; then
    echo "ERROR: NGC_API_KEY environment variable not set. Required for NIM."
    echo "Get your API key from: https://catalog.ngc.nvidia.com/"
    echo ""
    echo "To set your API key:"
    echo "  export NGC_API_KEY=your_key_here"
    echo ""
    echo "Or to skip NIM benchmarks, disable NIM in your config file."
    exit 1
fi

# Verify NGC_API_KEY is exported (not just defined)
if ! env | grep -q "^NGC_API_KEY="; then
    echo "ERROR: NGC_API_KEY is set but not exported."
    echo "Use: export NGC_API_KEY=your_key_here"
    exit 1
fi

# 2. Determine fastest storage location
echo "Determining optimal storage locations..."

# Primary drive is fastest but non-persistent
PRIMARY_DRIVE="/mnt/primary"
if [ -d "$PRIMARY_DRIVE" ]; then
    FAST_CACHE="$PRIMARY_DRIVE/openfold_cache"
    echo "Using primary drive for cache: $FAST_CACHE"
else
    FAST_CACHE="$HOME/openfold_cache"
    echo "Using home directory for cache: $FAST_CACHE"
fi

mkdir -p "$FAST_CACHE"

# Results should go to persistent storage
RESULTS_DIR="${PERSISTENT_VOLUME:-$HOME}/openfold_results"
mkdir -p "$RESULTS_DIR"
echo "Results directory (persistent): $RESULTS_DIR"

# 3. Create cache directories
mkdir -p "$FAST_CACHE/nim_cache"
mkdir -p "$FAST_CACHE/openfold_repo"
mkdir -p "$FAST_CACHE/datasets"

# 4. Check disk space (Fix #3: More robust disk space checks)
AVAILABLE_GB=$(df -BG "$FAST_CACHE" | tail -1 | awk '{print $4}' | sed 's/G//')
echo "Available disk space in $FAST_CACHE: ${AVAILABLE_GB}GB"

# Check /tmp space (often separate partition)
TMP_AVAILABLE_GB=$(df -BG /tmp 2>/dev/null | tail -1 | awk '{print $4}' | sed 's/G//' || echo "999")
echo "Available disk space in /tmp: ${TMP_AVAILABLE_GB}GB"

# Error if critically low space
if [ "$AVAILABLE_GB" -lt 50 ]; then
    echo "ERROR: Critically low disk space (${AVAILABLE_GB}GB available)."
    echo "Need at least 50GB, recommend 100GB for full benchmark."
    echo "Free up space or use a smaller config."
    echo ""
    echo "To override this check (not recommended):"
    echo "  SKIP_DISK_CHECK=1 $0"
    [ -z "$SKIP_DISK_CHECK" ] && exit 1
fi

# Warn if below recommended
if [ "$AVAILABLE_GB" -lt 100 ]; then
    echo "WARNING: Less than 100GB available (found ${AVAILABLE_GB}GB)."
    echo "Full benchmark requires ~100GB. Consider using smaller config or freeing space."
    echo "Continuing in 5 seconds... (Ctrl+C to cancel)"
    sleep 5
fi

# 5. Pre-pull large containers (optional, saves time)
echo "Pre-pulling NIM container (this may take 10-30 minutes)..."
docker pull nvcr.io/nim/openfold/openfold2:latest || echo "Container pull failed, will retry on first run"

# 6. Write environment file
cat > .env.colossus << EOF
# Colossus environment configuration
export FAST_CACHE=$FAST_CACHE
export RESULTS_DIR=$RESULTS_DIR
export NGC_API_KEY=${NGC_API_KEY:-}
export CUDA_VISIBLE_DEVICES=0
EOF

echo "Bootstrap complete!"
echo "Cache directory: $FAST_CACHE"
echo "Results directory: $RESULTS_DIR"
echo ""
echo "Next steps:"
echo "1. Source the environment: source .env.colossus"
echo "2. Install Python dependencies: pip install -e ."
echo "3. Run benchmark: ./scripts/run_all.sh"
