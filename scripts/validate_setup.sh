#!/bin/bash
# Validation script to verify setup before running benchmarks
# Run this after installation to ensure everything is configured correctly

set -e

echo "================================================"
echo "OpenFold2-NIM Benchmark Setup Validation"
echo "================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check Python version
echo "Checking Python version..."
python_version=$(python --version 2>&1 | awk '{print $2}')
if python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"; then
    check_pass "Python $python_version (>= 3.10 required)"
else
    check_fail "Python $python_version is too old (>= 3.10 required)"
fi

# Check bench CLI is installed
echo ""
echo "Checking bench CLI installation..."
if command -v bench &> /dev/null; then
    check_pass "bench CLI installed"
else
    check_fail "bench CLI not found. Run: pip install -e ."
fi

# Check Python dependencies
echo ""
echo "Checking Python dependencies..."
python -c "
import sys
required = ['typer', 'pydantic', 'yaml', 'pandas', 'plotly', 'rich', 'tabulate']
missing = []
for pkg in required:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)
if missing:
    print(f'Missing packages: {missing}')
    sys.exit(1)
"
if [ $? -eq 0 ]; then
    check_pass "All required Python packages installed"
else
    check_fail "Some Python packages missing. Run: pip install -e ."
fi

# Check dataset files
echo ""
echo "Checking dataset files..."
if [ -f "bench/dataset/targets.yaml" ]; then
    check_pass "Classic targets dataset found"
else
    check_fail "bench/dataset/targets.yaml not found"
fi

if [ -f "bench/dataset/casp15_targets.yaml" ]; then
    check_pass "CASP15 targets dataset found"
else
    check_warn "bench/dataset/casp15_targets.yaml not found (optional)"
fi

# Check config files
echo ""
echo "Checking configuration files..."
if [ -f "configs/default.yaml" ]; then
    check_pass "Default config found"
else
    check_fail "configs/default.yaml not found"
fi

if [ -f "configs/casp15.yaml" ]; then
    check_pass "CASP15 config found"
else
    check_warn "configs/casp15.yaml not found (optional)"
fi

# Check YAML syntax
echo ""
echo "Validating YAML syntax..."
python -c "
import yaml
try:
    with open('bench/dataset/targets.yaml') as f:
        yaml.safe_load(f)
    print('✓ targets.yaml is valid')
except Exception as e:
    print(f'✗ targets.yaml error: {e}')
    exit(1)
"

if [ -f "bench/dataset/casp15_targets.yaml" ]; then
    python -c "
import yaml
try:
    with open('bench/dataset/casp15_targets.yaml') as f:
        yaml.safe_load(f)
    print('✓ casp15_targets.yaml is valid')
except Exception as e:
    print(f'✗ casp15_targets.yaml error: {e}')
    exit(1)
"
fi

# Check GPU availability (optional)
echo ""
echo "Checking GPU availability (optional)..."
if command -v nvidia-smi &> /dev/null; then
    gpu_count=$(nvidia-smi --list-gpus 2>/dev/null | wc -l)
    if [ "$gpu_count" -gt 0 ]; then
        check_pass "Found $gpu_count GPU(s)"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1
    else
        check_warn "nvidia-smi found but no GPUs detected"
    fi
else
    check_warn "nvidia-smi not found (required for GPU monitoring)"
fi

# Check Docker (optional for NIM)
echo ""
echo "Checking Docker (optional for NIM)..."
if command -v docker &> /dev/null; then
    if docker ps &> /dev/null; then
        check_pass "Docker is running and accessible"
    else
        check_warn "Docker found but not accessible (may need sudo or user in docker group)"
    fi
else
    check_warn "Docker not found (required for NIM benchmarks)"
fi

# Check NGC_API_KEY (optional for NIM)
echo ""
echo "Checking NGC_API_KEY (optional for NIM)..."
if [ -n "$NGC_API_KEY" ]; then
    check_pass "NGC_API_KEY is set"
else
    check_warn "NGC_API_KEY not set (required for NIM benchmarks)"
fi

# Check disk space
echo ""
echo "Checking disk space..."
free_space=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$free_space" -ge 100 ]; then
    check_pass "Sufficient disk space: ${free_space}GB available"
else
    check_warn "Low disk space: ${free_space}GB available (recommend 100GB+)"
fi

# Test import of new modules
echo ""
echo "Testing new analysis modules..."
python -c "
try:
    from bench.analysis.export import export_all_csvs
    from bench.analysis.markdown import generate_results_markdown
    print('✓ CSV export and markdown modules import successfully')
except ImportError as e:
    print(f'✗ Import error: {e}')
    exit(1)
"

echo ""
echo "================================================"
echo -e "${GREEN}Setup validation complete!${NC}"
echo "================================================"
echo ""
echo "Next steps:"
echo "  1. Run preflight checks: bench preflight"
echo "  2. Run quick benchmark: bench run --config configs/default.yaml"
echo "  3. Run CASP15 benchmark: bench run --config configs/casp15.yaml"
echo ""
