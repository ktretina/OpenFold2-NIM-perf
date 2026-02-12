# Quick Reference Card

## Initial Setup (5 minutes)

```bash
# 1. Set NGC API key
export NGC_API_KEY="nvapi-..."

# 2. Clone and bootstrap
git clone https://github.com/ktretina/OpenFold2-NIM-perf.git
cd OpenFold2-NIM-perf
./scripts/colossus/bootstrap.sh
source .env.colossus

# 3. Validate (optional but recommended)
./scripts/colossus/validate.sh
```

## Running Benchmarks

```bash
# Quick test (2 min)
bench run --config configs/smoke_test.yaml

# Default benchmark (30 min)
bench run --config configs/default.yaml

# CASP15 (3-4 hours)
bench run --config configs/casp15.yaml

# One-click with auto-config
./scripts/colossus/run.sh configs/casp15.yaml
```

## Hardware Detection

```bash
# Detect hardware
bench colossus detect

# Generate optimized config
bench colossus auto-config --base-config configs/default.yaml

# Generated configs appear in:
ls configs/generated/
```

## Campaign Mode

```bash
# Create campaign
bench colossus campaign-create campaigns/gpu_study

# Add runs
bench colossus campaign-add --campaign-dir campaigns/gpu_study \
  --run-dir results/run_*

# Aggregate and report
bench colossus campaign-aggregate campaigns/gpu_study
bench colossus campaign-report campaigns/gpu_study

# View report
open campaigns/gpu_study/campaign_report.html
```

## Analysis

```bash
# Analyze latest results
bench analyze results/latest

# View HTML report
open results/latest/analysis/report.html

# View specific run
bench analyze results/run_20260211_123456
```

## Available Configurations

| Config | Runtime | Description |
|--------|---------|-------------|
| `smoke_test.yaml` | 2 min | Quick validation (2 proteins, NIM only) |
| `default.yaml` | 30 min | Default benchmark (5 proteins, both systems) |
| `casp15.yaml` | 3-4 hrs | CASP15 targets (18 proteins, research-grade) |
| `statistical_rigor.yaml` | 8 hrs | Publication quality (20 passes, shuffling) |
| `world_class_benchmark.yaml` | 12+ hrs | Comprehensive (multiple suites) |
| `inference_only_benchmark.yaml` | 4 hrs | Precomputed MSAs (apples-to-apples) |
| `nim_backend_comparison.yaml` | 2 hrs | TensorRT vs Torch |
| `cold_start.yaml` | 1 hr | Container startup overhead |

## Troubleshooting

```bash
# Check environment
env | grep -E "(NGC|FAST|PERSIST)"

# Check GPU
nvidia-smi

# Check disk space
df -h /mnt/primary $HOME

# Check Docker
docker ps

# Preflight validation
bench preflight

# Full validation
./scripts/colossus/validate.sh

# View logs
tail -f results/*/benchmark.log
```

## Common Commands

```bash
# Version pinning
./scripts/colossus/pin_versions.sh

# Test deployment
./scripts/colossus/test_deployment.sh

# Hardware info
bench colossus detect

# List all CLI commands
bench --help
bench colossus --help
```

## Environment Variables

```bash
# Required
NGC_API_KEY          # NGC registry access

# Auto-set by bootstrap
FAST_WORKDIR         # Fast storage (/mnt/primary)
PERSIST_DIR          # Persistent storage ($HOME/results)

# Optional
AUTO_DETECT=true     # Enable auto-config
SKIP_VALIDATION=false # Skip validation step
CHECKPOINT=true      # Enable checkpointing
PUSH_RESULTS=false   # Enable Git sync
```

## File Locations

```
/mnt/primary/              # Fast storage (ephemeral)
  ├── openfold_workdir/    # Work files
  └── nim_cache/           # NIM cache

$HOME/                     # Persistent storage
  └── openfold_results/    # Results
      └── run_*/
          ├── manifest.json
          ├── records.parquet
          ├── benchmark.log
          └── analysis/
              └── report.html
```

## Quick Diagnostics

| Check | Command | Expected |
|-------|---------|----------|
| NGC key | `echo $NGC_API_KEY` | nvapi-... |
| GPU | `nvidia-smi` | Shows GPU info |
| Docker | `docker ps` | Shows containers |
| Bench CLI | `bench --version` | Shows version |
| Python | `python3 --version` | 3.10+ |
| Storage | `df -h /mnt/primary` | 100+ GB free |

## Performance Tips

1. **Use fast storage:** FAST_WORKDIR=/mnt/primary (not $HOME)
2. **Single model first:** Start with configs using model_sets: [[3]]
3. **Reduce MSA depth:** Use msa_depth: 1 for quick tests
4. **Monitor GPU:** Run `nvidia-smi -l 1` in another terminal
5. **Check logs:** tail -f results/*/benchmark.log

## Emergency Stops

```bash
# Stop running benchmark
Ctrl+C

# Kill stuck Docker container
docker ps
docker stop <container-id>

# Free up GPU
nvidia-smi
kill <process-id>

# Clean up disk space
docker system prune -a
rm -rf $FAST_WORKDIR/*
```

## Documentation Links

- **Deployment:** [COLOSSUS_DEPLOY.md](COLOSSUS_DEPLOY.md)
- **User Guide:** [docs/COLOSSUS_QUICKSTART.md](docs/COLOSSUS_QUICKSTART.md)
- **Operations:** [docs/COLOSSUS_RUNBOOK.md](docs/COLOSSUS_RUNBOOK.md)
- **Technical:** [docs/IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md)
- **Checklist:** [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

---

**Need help?** See troubleshooting section in COLOSSUS_DEPLOY.md
