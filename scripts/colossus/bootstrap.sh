#!/bin/bash
# Bootstrap script for Colossus benchmark environment
#
# This script sets up the environment with retry logic and actionable errors
#
# Features:
# - Retry transient failures (network, Docker registry)
# - Actionable error messages with fix hints
# - Validation of all prerequisites
# - Environment file creation (.env.colossus)

set -e

RETRY_COUNT=${RETRY_COUNT:-3}
RETRY_DELAY=${RETRY_DELAY:-5}

echo "============================================================"
echo "OpenFold2-NIM Benchmark - Bootstrap"
echo "============================================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Retry wrapper function
retry() {
    local cmd="$1"
    local description="$2"
    local attempt=1

    while [ $attempt -le $RETRY_COUNT ]; do
        echo "[$attempt/$RETRY_COUNT] $description..."
        if eval "$cmd" 2>&1; then
            echo -e "${GREEN}✓ $description succeeded${NC}"
            return 0
        else
            if [ $attempt -lt $RETRY_COUNT ]; then
                echo -e "${YELLOW}⚠ Retrying in ${RETRY_DELAY}s...${NC}"
                sleep $RETRY_DELAY
            fi
        fi
        attempt=$((attempt + 1))
    done
    echo -e "${RED}✗ $description failed after $RETRY_COUNT attempts${NC}"
    return 1
}

# Check command availability
check_command() {
    local cmd="$1"
    local name="$2"
    local install_hint="$3"

    if ! command -v "$cmd" &> /dev/null; then
        echo -e "${RED}✗ $name not found${NC}"
        echo "  To install: $install_hint"
        return 1
    fi
    echo -e "${GREEN}✓ $name found${NC}"
    return 0
}

# Phase 1: Check prerequisites
echo "=== Phase 1: Checking Prerequisites ==="
echo ""

ALL_CHECKS_PASSED=true

# Check nvidia-smi
check_command nvidia-smi "NVIDIA drivers" \
    "Install from https://www.nvidia.com/drivers" || ALL_CHECKS_PASSED=false

# Check Docker
check_command docker "Docker" \
    "Install from https://docs.docker.com/get-docker/" || ALL_CHECKS_PASSED=false

# Check Python
check_command python3 "Python 3" \
    "Install Python 3.10+: https://www.python.org/downloads/" || ALL_CHECKS_PASSED=false

# Check NGC_API_KEY
if [ -z "$NGC_API_KEY" ]; then
    echo -e "${RED}✗ NGC_API_KEY not set${NC}"
    echo "  To set: export NGC_API_KEY='your-api-key'"
    echo "  Get key from: https://catalog.ngc.nvidia.com/"
    ALL_CHECKS_PASSED=false
else
    echo -e "${GREEN}✓ NGC_API_KEY is set${NC}"
fi

if [ "$ALL_CHECKS_PASSED" = false ]; then
    echo ""
    echo -e "${RED}✗ Some prerequisites are missing. Fix issues above.${NC}"
    exit 1
fi

echo ""

# Phase 2: Docker setup
echo "=== Phase 2: Docker Setup ==="
echo ""

# Check Docker daemon
if ! docker ps &> /dev/null; then
    echo -e "${RED}✗ Docker daemon not accessible${NC}"
    echo "  Start Docker: sudo systemctl start docker"
    echo "  Check permissions: sudo usermod -aG docker $USER"
    exit 1
fi
echo -e "${GREEN}✓ Docker daemon is accessible${NC}"

# Login to NGC (with retry)
echo ""
echo "Logging in to NVIDIA NGC registry..."
retry "echo \$NGC_API_KEY | docker login nvcr.io --username '\$oauthtoken' --password-stdin" \
    "NGC registry login"

echo ""

# Phase 3: Pull NIM container (with retry)
echo "=== Phase 3: Pulling NIM Container ==="
echo ""
echo "This may take several minutes on first run..."
echo ""

retry "docker pull nvcr.io/nim/openfold/openfold2:latest" \
    "NIM container pull" || {
    echo ""
    echo -e "${RED}✗ Failed to pull NIM container${NC}"
    echo "  Check NGC_API_KEY is valid"
    echo "  Check network connectivity"
    echo "  Try manually: docker pull nvcr.io/nim/openfold/openfold2:latest"
    exit 1
}

echo ""

# Phase 4: Detect storage
echo "=== Phase 4: Detecting Storage ==="
echo ""

# Detect fast storage
FAST_WORKDIR=""
if [ -d "/mnt/primary" ]; then
    FAST_WORKDIR="/mnt/primary/openfold_workdir"
    echo -e "${GREEN}✓ Detected Colossus primary storage: /mnt/primary${NC}"
elif [ -d "/mnt/nvme" ]; then
    FAST_WORKDIR="/mnt/nvme/openfold_workdir"
    echo -e "${GREEN}✓ Detected NVMe storage: /mnt/nvme${NC}"
else
    FAST_WORKDIR="$HOME/openfold_workdir"
    echo -e "${YELLOW}⚠ Using home directory for work files: $HOME${NC}"
    echo "  For better performance, mount fast storage (NVMe/SSD)"
fi

# Persistent storage (always home for results)
PERSIST_DIR="$HOME/openfold_results"

echo "  Fast workdir:     $FAST_WORKDIR"
echo "  Persistent dir:   $PERSIST_DIR"

# Check available space
AVAILABLE_GB=$(df -BG "$HOME" | tail -1 | awk '{print $4}' | sed 's/G//')
echo "  Available space:  ${AVAILABLE_GB}GB"

if [ "$AVAILABLE_GB" -lt 100 ]; then
    echo -e "${YELLOW}⚠ Low disk space (${AVAILABLE_GB}GB). Recommend 100+ GB free.${NC}"
fi

echo ""

# Phase 5: Create environment file
echo "=== Phase 5: Creating Environment File ==="
echo ""

cat > .env.colossus << EOF
# Colossus environment configuration
# Generated on $(date)

# Storage paths
export FAST_WORKDIR="$FAST_WORKDIR"
export PERSIST_DIR="$PERSIST_DIR"

# NGC credentials (already set in environment)
# export NGC_API_KEY="your-key-here"

# Python environment
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}\$(pwd)"
EOF

echo -e "${GREEN}✓ Environment file created: .env.colossus${NC}"
echo ""
echo "To activate:"
echo "  source .env.colossus"
echo ""

# Phase 6: Verify installation
echo "=== Phase 6: Verification ==="
echo ""

# Check GPU
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1

echo ""
echo "============================================================"
echo -e "${GREEN}✓ Bootstrap Complete!${NC}"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Activate environment:  source .env.colossus"
echo "  2. Run benchmark:         ./scripts/colossus/run.sh"
echo ""
