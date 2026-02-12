# Colossus Deployment Guide - Push Button Setup

This guide will get you from zero to running benchmarks on NVIDIA Colossus in **under 5 minutes**.

## Prerequisites

- Colossus GPU instance (H100, A100, or L40S)
- NGC API key ([get one here](https://catalog.ngc.nvidia.com/))
- SSH access to Colossus machine

## Quick Start (3 Commands)

```bash
# 1. Set NGC API key
export NGC_API_KEY="your-api-key-here"

# 2. Clone repository
git clone https://github.com/ktretina/OpenFold2-NIM-perf.git
cd OpenFold2-NIM-perf

# 3. Run bootstrap (handles everything)
./scripts/colossus/bootstrap.sh
source .env.colossus
```

**That's it!** The bootstrap script will:
- ✅ Verify prerequisites (drivers, Docker, etc.)
- ✅ Login to NGC registry
- ✅ Pull NIM container (~10GB, may take 5-10 minutes)
- ✅ Detect optimal storage paths
- ✅ Install Python dependencies
- ✅ Create environment file

---

## Validation (Optional but Recommended)

Before running a long benchmark, validate the installation:

```bash
./scripts/colossus/validate.sh
```

This runs ~30 tests covering:
- System requirements (drivers, Docker, Python)
- Python dependencies (pydantic, pandas, etc.)
- Benchmark package installation
- Colossus modules (checkpoint, hardware detection, campaign)
- Configuration files
- Hardware detection

**Expected output:**
```
============================================================
Validation Results
============================================================

Passed:  25
Warned:  3
Failed:  0

✓ All critical tests passed!
```

---

## Smoke Test (2 Minutes)

Run a quick smoke test to verify end-to-end functionality:

```bash
bench run --config configs/smoke_test.yaml
```

This runs:
- 2 tiny proteins (50aa, 100aa)
- NIM only (TensorRT backend)
- Single model (model_3)
- No warmup, 1 measurement pass
- **Runtime: ~1-2 minutes**

**Expected output:**
```
✓ Benchmark complete!
  Run ID: run_20260211_123456
  Results: results/smoke_test/run_20260211_123456
  Records: 2
```

If this completes successfully, your installation is working!

---

## Running Production Benchmarks

### Option 1: One-Click Auto-Config (Recommended)

Let the system detect your hardware and optimize settings:

```bash
./scripts/colossus/run.sh configs/default.yaml
```

This automatically:
1. Detects GPU type, VRAM, storage
2. Generates optimized config
3. Validates environment
4. Runs benchmark

### Option 2: Manual Configuration

For more control:

```bash
# Detect hardware
bench colossus detect

# Generate optimized config
bench colossus auto-config --base-config configs/default.yaml --output-dir configs/generated

# Run with generated config
bench run --config configs/generated/auto_h100.yaml

# Analyze results
bench analyze results/latest
open results/latest/analysis/report.html
```

---

## Available Benchmark Configurations

### Quick Tests (< 1 hour)

**Default Benchmark** (~30 minutes)
```bash
bench run --config configs/default.yaml
```
- 5 classic proteins
- Single model comparison (NIM vs OpenFold)
- 3 measurement passes

**Smoke Test** (~2 minutes)
```bash
bench run --config configs/smoke_test.yaml
```
- 2 tiny proteins
- NIM only, minimal settings
- For validation only

### Research Benchmarks (2-8 hours)

**CASP15** (~3-4 hours)
```bash
bench run --config configs/casp15.yaml
```
- 18 CASP15 targets
- Single model, MSA depth 128
- Research-grade accuracy metrics

**Statistical Rigor** (~8 hours)
```bash
bench run --config configs/statistical_rigor.yaml
```
- 10 warmup passes
- 20 measurement passes
- Target shuffling
- Publication-quality statistics

**World-Class Comprehensive** (~12+ hours)
```bash
bench run --config configs/world_class_benchmark.yaml
```
- Multiple benchmark suites
- MSA scaling, sequence length scaling
- Full ensemble (5 models)
- Comprehensive metrics

### Specialized Benchmarks

**Inference Only** (apples-to-apples)
```bash
bench run --config configs/inference_only_benchmark.yaml
```
- Uses precomputed MSAs
- Identical inputs for NIM and OpenFold
- Pure inference comparison

**Backend Comparison** (TensorRT vs Torch)
```bash
# Run TensorRT
bench run --config configs/nim_backend_comparison.yaml

# Edit config, change backend to "torch", run again
# Then compare results
```

**Cold Start** (microservice overhead)
```bash
bench run --config configs/cold_start.yaml
```
- Measures container startup time
- First vs second request latency
- NIM-specific

---

## Campaign Mode (Multi-GPU Studies)

To compare performance across GPU types:

```bash
# 1. Create campaign
bench colossus campaign-create campaigns/gpu_comparison --name "H100 vs A100"

# 2. Run on H100
bench run --config configs/generated/auto_h100.yaml
bench colossus campaign-add --campaign-dir campaigns/gpu_comparison --run-dir results/latest

# 3. Run on A100 (after switching to A100 instance)
bench run --config configs/generated/auto_a100.yaml
bench colossus campaign-add --campaign-dir campaigns/gpu_comparison --run-dir results/latest

# 4. Aggregate and generate comparison report
bench colossus campaign-aggregate campaigns/gpu_comparison
bench colossus campaign-report campaigns/gpu_comparison

# 5. View comparison
open campaigns/gpu_comparison/campaign_report.html
```

---

## Troubleshooting

### Bootstrap Fails

**"NGC_API_KEY not set"**
```bash
export NGC_API_KEY="your-key-here"
# Verify
echo $NGC_API_KEY
```

**"Docker daemon not accessible"**
```bash
sudo systemctl start docker
sudo usermod -aG docker $USER
# Log out and back in
```

**"Container pull failed"**
- Check network connectivity
- Verify NGC_API_KEY is valid
- Try manual pull: `docker pull nvcr.io/nim/openfold/openfold2:latest`

### Validation Fails

**"Import errors"**
```bash
# Reinstall dependencies
pip3 install -e .

# Check specific package
python3 -c "import pydantic"
```

**"bench command not found"**
```bash
# Source environment
source .env.colossus

# Or reinstall
pip3 install -e .
```

### Benchmark Fails

**"CUDA out of memory"**
- Reduce MSA depth in config
- Use single model instead of ensemble
- Check no other processes using GPU: `nvidia-smi`

**"Permission denied"**
- Check file permissions: `ls -la scripts/colossus/`
- Make executable: `chmod +x scripts/colossus/*.sh`

**"Slow performance"**
- Verify using fast storage: `echo $FAST_WORKDIR`
- Should be `/mnt/primary` on Colossus, not home directory
- Check with: `df -h /mnt/primary`

---

## Storage Best Practices

### Colossus Storage Hierarchy

1. **Primary drive** (`/mnt/primary`) - **FASTEST**, non-persistent
   - Use for: NIM cache, MSA temp files, working directory
   - Lost on machine release

2. **Home directory** (`$HOME`) - Persistent, reasonable speed
   - Use for: Final results, checkpoints, analysis

3. **Volumes** - Persistent, network-dependent
   - Use for: Long-term storage, cross-machine sharing

### Automatic Configuration

Bootstrap script detects and sets:
```bash
FAST_WORKDIR=/mnt/primary/openfold_workdir  # Fast, ephemeral
PERSIST_DIR=$HOME/openfold_results           # Persistent
```

To override:
```bash
export FAST_WORKDIR="/your/fast/path"
export PERSIST_DIR="/your/persistent/path"
./scripts/colossus/run.sh
```

---

## Version Pinning for Reproducibility

Capture exact versions for reproducibility:

```bash
./scripts/colossus/pin_versions.sh my_versions.yaml
```

This captures:
- NIM container digest (`sha256:...`)
- OpenFold git commit hash
- Benchmark code commit
- Python dependencies

Use in config:
```yaml
nim:
  container_registry_digest: "sha256:..."  # From pin_versions.sh

openfold:
  commit_hash: "abc123..."  # From pin_versions.sh
```

---

## Complete Example Session

From fresh Colossus instance to completed benchmark:

```bash
# === Setup (5-10 minutes, one time) ===

# Set NGC key
export NGC_API_KEY="nvapi-..."

# Clone and bootstrap
git clone https://github.com/ktretina/OpenFold2-NIM-perf.git
cd OpenFold2-NIM-perf
./scripts/colossus/bootstrap.sh
source .env.colossus

# Validate installation
./scripts/colossus/validate.sh

# Quick smoke test (2 min)
bench run --config configs/smoke_test.yaml

# === Production Benchmark (30 min - 4 hours) ===

# Auto-config and run
./scripts/colossus/run.sh configs/casp15.yaml

# Results appear at:
# $HOME/openfold_results/run_20260211_*/

# === Analysis ===

bench analyze results/latest
open results/latest/analysis/report.html

# === Done! ===
```

---

## Environment Variables Reference

Set these before running benchmarks:

```bash
# Required
NGC_API_KEY          # NGC API key for NIM container access

# Recommended (auto-set by bootstrap)
FAST_WORKDIR         # Fast storage path (e.g., /mnt/primary/workdir)
PERSIST_DIR          # Persistent results path (e.g., $HOME/results)

# Optional
AUTO_DETECT=true     # Enable hardware auto-detection (default: true)
CHECKPOINT=true      # Enable checkpointing (default: true)
PUSH_RESULTS=false   # Enable Git sync (default: false)
```

---

## File Locations After Bootstrap

```
OpenFold2-NIM-perf/
├── .env.colossus              # Environment variables
├── scripts/colossus/
│   ├── bootstrap.sh           # Setup script
│   ├── run.sh                 # One-click runner
│   └── validate.sh            # Validation script
├── configs/
│   ├── default.yaml           # Quick benchmark
│   ├── smoke_test.yaml        # 2-min validation
│   ├── casp15.yaml            # Research benchmark
│   └── generated/             # Auto-generated configs
│       └── auto_h100.yaml
└── results/                   # Default output (or $PERSIST_DIR)
    └── run_*/
        ├── manifest.json
        ├── records.parquet
        └── analysis/
            └── report.html
```

---

## Getting Help

- **Quick Start:** This file (COLOSSUS_DEPLOY.md)
- **User Guide:** [docs/COLOSSUS_QUICKSTART.md](docs/COLOSSUS_QUICKSTART.md)
- **Operations:** [docs/COLOSSUS_RUNBOOK.md](docs/COLOSSUS_RUNBOOK.md)
- **Technical Details:** [docs/IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md)
- **Methodology:** [docs/WORLD_CLASS_METHODOLOGY.md](docs/WORLD_CLASS_METHODOLOGY.md)

---

## Success Criteria

After following this guide, you should have:

- ✅ All dependencies installed
- ✅ NGC container pulled
- ✅ Environment configured
- ✅ Validation passing (25+ tests)
- ✅ Smoke test completed (2 minutes)
- ✅ Ready to run production benchmarks

**Time Investment:**
- Bootstrap: 5-10 minutes (one time)
- Validation: 1 minute
- Smoke test: 2 minutes
- **Total: ~10-15 minutes to production-ready**

---

## What's Next?

1. **Run your first benchmark:**
   ```bash
   ./scripts/colossus/run.sh configs/casp15.yaml
   ```

2. **Explore different configurations:**
   - Try `configs/statistical_rigor.yaml` for publication quality
   - Try `configs/world_class_benchmark.yaml` for comprehensive analysis

3. **Multi-GPU campaign:**
   - Compare H100 vs A100 performance
   - Use campaign mode for cross-GPU analysis

4. **Customize:**
   - Create your own target proteins
   - Adjust warmup/measurement passes
   - Try different model sets

Happy benchmarking on Colossus! 🚀
