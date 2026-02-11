# Colossus Quick Start Guide

Get started with the OpenFold2-NIM benchmark suite on Colossus in 5 minutes.

## Prerequisites

- Colossus GPU instance (H100, A100, or L40S)
- NGC API key ([get one here](https://catalog.ngc.nvidia.com/))

## One-Command Quick Start

```bash
# Export NGC key
export NGC_API_KEY="your-api-key-here"

# Clone and run
git clone <repo-url>
cd openfold2nim_perf

# One command to run everything!
./scripts/colossus/run.sh
```

This automatically:
1. ✅ Bootstraps environment (first time only)
2. ✅ Detects your GPU and storage
3. ✅ Generates optimized config
4. ✅ Validates prerequisites
5. ✅ Runs benchmark

Results will be in `$HOME/openfold_results/run_*/`

---

## Manual Workflow

### 1. Bootstrap (First Time Only)

```bash
./scripts/colossus/bootstrap.sh
source .env.colossus
```

This sets up:
- NGC Docker login
- NIM container pre-pull
- Storage path detection
- Environment variables

### 2. Detect Hardware

```bash
bench colossus detect
```

Output:
```
============================================================
HARDWARE DETECTION SUMMARY
============================================================
GPU Model:          H100
GPU VRAM:           80 GB
Fast Storage:       /mnt/primary
Available Space:    2500.0 GB

RECOMMENDATIONS:
  Model Sets:       [[3], [1, 2, 3, 4, 5]]
  Warmup Passes:    3
  Measurement:      10
============================================================
```

### 3. Generate Config

```bash
bench colossus auto-config --base-config configs/default.yaml
```

Creates: `configs/generated/auto_h100.yaml` (or `auto_a100.yaml`, etc.)

### 4. Validate Environment

```bash
bench preflight
```

Checks:
- ✅ NVIDIA drivers
- ✅ Docker daemon
- ✅ NGC API key
- ✅ GPU visibility
- ✅ Disk space

### 5. Run Benchmark

```bash
bench run --config configs/generated/auto_h100.yaml
```

Runtime: ~2-4 hours for full benchmark

### 6. View Results

```bash
bench analyze results/latest
open results/latest/analysis/report.html
```

---

## Common Configurations

### Quick Test (5 minutes)

```bash
bench run --config configs/default.yaml
```

- 5 targets
- Single model (model_3)
- MSA depth: 1
- 3 measurement passes

### CASP15 Benchmark (3-4 hours)

```bash
bench run --config configs/casp15.yaml
```

- 18 CASP15 targets
- Single model (model_3)
- MSA depth: 128
- 3 measurement passes

### Statistical Rigor (8+ hours)

```bash
bench run --config configs/statistical_rigor.yaml
```

- 18 CASP15 targets
- 10 warmup passes
- 20 measurement passes
- Target shuffling enabled

### World-Class Comprehensive

```bash
bench run --config configs/world_class_benchmark.yaml
```

- Multiple suites (accuracy, MSA scaling, sequence length)
- Full ensemble (models 1-5)
- Precomputed MSAs for reproducibility
- Publication-quality metrics

---

## Campaign Mode (Multi-GPU Study)

Compare performance across GPU types:

```bash
# Create campaign
bench colossus campaign-create campaigns/gpu_comparison \
  --name "H100 vs A100 Performance"

# Run on H100
bench run --config configs/auto_h100.yaml
bench colossus campaign-add \
  --campaign-dir campaigns/gpu_comparison \
  --run-dir results/run_h100_*

# Run on A100 (after switching instance)
bench run --config configs/auto_a100.yaml
bench colossus campaign-add \
  --campaign-dir campaigns/gpu_comparison \
  --run-dir results/run_a100_*

# Aggregate and compare
bench colossus campaign-aggregate campaigns/gpu_comparison
bench colossus campaign-report campaigns/gpu_comparison

# View comparison
open campaigns/gpu_comparison/campaign_report.html
```

---

## Advanced Features

### Version Pinning for Reproducibility

```bash
# Capture current versions
./scripts/colossus/pin_versions.sh my_versions.yaml

# Edit config to use pinned versions
vim configs/my_config.yaml
```

```yaml
nim:
  container_image: "nvcr.io/nim/openfold/openfold2:latest"
  container_registry_digest: "sha256:..."  # From pin_versions.sh
  warn_on_latest_tag: false

openfold:
  commit_hash: "..."  # From pin_versions.sh
```

### Custom Storage Paths

```bash
export FAST_WORKDIR="/mnt/primary/my_workdir"
export PERSIST_DIR="$HOME/my_results"

bench run --config configs/default.yaml
```

### Resume Interrupted Run (Coming Soon)

```bash
# Start run
bench run --config configs/casp15.yaml --checkpoint

# If interrupted (Ctrl+C or crash)...

# Resume from checkpoint
bench run --config configs/casp15.yaml --checkpoint --resume
```

---

## Troubleshooting

### "NGC_API_KEY not set"

```bash
export NGC_API_KEY="your-api-key"
# Verify
echo $NGC_API_KEY
```

### "Docker daemon not accessible"

```bash
# Start Docker
sudo systemctl start docker

# Check permissions
sudo usermod -aG docker $USER
# Then log out and back in
```

### "No GPUs detected"

```bash
# Check driver
nvidia-smi

# Check CUDA visibility
echo $CUDA_VISIBLE_DEVICES
# Should be empty or "0,1,2,..." for multi-GPU
```

### "Low disk space"

```bash
# Check available space
df -h $HOME

# Free up space or use external storage
export FAST_WORKDIR="/path/to/fast/storage"
export PERSIST_DIR="/path/to/large/storage"
```

### "Import errors"

```bash
# Install dependencies
pip install -e .

# Or with plot support
pip install -e ".[plots]"
```

---

## Storage Best Practices on Colossus

### Storage Hierarchy (Fastest → Slowest)

1. **Primary drive** (`/mnt/primary`) - FASTEST, non-persistent
   - Use for: NIM cache, MSA temp files, model weights
   - Lost on machine release

2. **Home directory** (`$HOME`) - Persistent, reasonable speed
   - Use for: Final results, checkpoints, analysis

3. **Volumes** - Persistent, network-dependent
   - Use for: Long-term storage, cross-machine sharing

### Recommended Configuration

```bash
# In .env.colossus (auto-generated by bootstrap)
export FAST_WORKDIR="/mnt/primary/openfold_workdir"  # Fast, ephemeral
export PERSIST_DIR="$HOME/openfold_results"          # Persistent
```

This gives you:
- 10-100x faster I/O for MSA generation and model loading
- Persistent results that survive machine release

---

## Environment Variables Reference

```bash
# Storage paths
FAST_WORKDIR      # Fast storage for ephemeral work files
PERSIST_DIR       # Persistent storage for final results

# NGC credentials
NGC_API_KEY       # Required for NIM container access

# Benchmark options
AUTO_DETECT       # Enable hardware auto-config (default: true)
CHECKPOINT        # Enable checkpointing (default: true)
PUSH_RESULTS      # Enable Git sync (default: false)
```

---

## CLI Commands Reference

```bash
# Main commands
bench preflight                    # Validate environment
bench run --config <config>        # Run benchmark
bench analyze <results-dir>        # Generate analysis

# Colossus commands
bench colossus detect              # Detect hardware
bench colossus auto-config         # Generate optimized config

# Campaign commands
bench colossus campaign-create <dir> --name "Study Name"
bench colossus campaign-add --campaign-dir <dir> --run-dir <run>
bench colossus campaign-aggregate <dir>
bench colossus campaign-report <dir>
```

---

## Getting Help

- **Full documentation:** [docs/](../docs/)
- **Colossus runbook:** [COLOSSUS_RUNBOOK.md](COLOSSUS_RUNBOOK.md)
- **Methodology:** [WORLD_CLASS_METHODOLOGY.md](WORLD_CLASS_METHODOLOGY.md)
- **Metrics reference:** [METRICS_SCHEMA.md](METRICS_SCHEMA.md)
- **Implementation details:** [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

---

## Quick Tips

1. **Always run preflight checks first:**
   ```bash
   bench preflight
   ```

2. **Use auto-config for optimal settings:**
   ```bash
   bench colossus auto-config --base-config configs/default.yaml
   ```

3. **Start with a quick test:**
   ```bash
   bench run --config configs/default.yaml
   ```

4. **View results as HTML report:**
   ```bash
   bench analyze results/latest
   open results/latest/analysis/report.html
   ```

5. **Pin versions for reproducibility:**
   ```bash
   ./scripts/colossus/pin_versions.sh
   ```

6. **Use campaign mode for GPU comparisons:**
   ```bash
   bench colossus campaign-create campaigns/my_study
   ```

---

## Next Steps

After your first successful run:

1. **Explore configurations** - Try CASP15, statistical rigor, or world-class configs
2. **Compare backends** - Test TensorRT vs Torch
3. **Run campaign** - Compare H100 vs A100 performance
4. **Customize** - Create your own config for specific targets
5. **Contribute** - Share results and improvements

Happy benchmarking! 🚀
