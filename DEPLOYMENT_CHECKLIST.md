# Deployment Checklist

Use this checklist to verify the OpenFold2-NIM benchmark suite is production-ready on Colossus.

## Pre-Deployment (Before Cloning)

- [ ] Colossus GPU instance leased (H100, A100, or L40S)
- [ ] NGC API key obtained from https://catalog.ngc.nvidia.com/
- [ ] SSH access to Colossus machine verified
- [ ] At least 100GB free disk space available
- [ ] Network connectivity confirmed (for Docker pulls)

## Initial Setup

- [ ] Repository cloned: `git clone https://github.com/ktretina/OpenFold2-NIM-perf.git`
- [ ] Changed to repo directory: `cd OpenFold2-NIM-perf`
- [ ] NGC_API_KEY exported: `export NGC_API_KEY="..."`
- [ ] Bootstrap script executed: `./scripts/colossus/bootstrap.sh`
- [ ] Environment file created: `.env.colossus` exists
- [ ] Environment sourced: `source .env.colossus`

## Validation

Run validation script: `./scripts/colossus/validate.sh`

### System Requirements
- [ ] NVIDIA drivers accessible (nvidia-smi works)
- [ ] Docker installed (docker --version)
- [ ] Docker daemon running (docker ps)
- [ ] Python 3.10+ installed

### Environment Variables
- [ ] NGC_API_KEY set and exported
- [ ] FAST_WORKDIR set (usually /mnt/primary)
- [ ] PERSIST_DIR set (usually $HOME/openfold_results)

### Python Dependencies
- [ ] pydantic installed
- [ ] typer installed
- [ ] pandas installed
- [ ] numpy installed
- [ ] docker-py installed
- [ ] py3nvml installed (warning OK if missing)
- [ ] plotly installed (warning OK if missing)

### Benchmark Package
- [ ] bench CLI command available
- [ ] bench.config module imports
- [ ] bench.orchestrator module imports
- [ ] bench.colossus module imports

### Colossus Modules
- [ ] checkpoint module imports
- [ ] hardware_detect module imports
- [ ] auto_config module imports
- [ ] campaign module imports

### Configuration Files
- [ ] configs/default.yaml exists
- [ ] configs/smoke_test.yaml exists
- [ ] configs/casp15.yaml exists
- [ ] Configuration loads without errors

### Scripts
- [ ] scripts/colossus/run.sh executable
- [ ] scripts/colossus/bootstrap.sh executable
- [ ] scripts/colossus/validate.sh executable
- [ ] scripts/colossus/test_deployment.sh executable

### Hardware Detection
- [ ] Hardware detection runs: `bench colossus detect`
- [ ] GPU model detected correctly
- [ ] VRAM capacity correct
- [ ] Fast storage path valid
- [ ] Recommendations reasonable

### Preflight Checks
- [ ] All preflight checks pass: `bench preflight`
- [ ] (Or at least no critical failures)

## Smoke Test (Recommended)

Run quick validation benchmark: `bench run --config configs/smoke_test.yaml`

- [ ] Benchmark starts without errors
- [ ] NIM container starts (or pulls if needed)
- [ ] Predictions complete (2 targets)
- [ ] Results written to disk
- [ ] Records file created (records.parquet)
- [ ] Manifest created (manifest.json)
- [ ] Analysis runs: `bench analyze results/smoke_test/run_*`
- [ ] HTML report generated

**Expected runtime:** 1-2 minutes
**Expected records:** 2

## Production Readiness

### One-Click Execution
- [ ] One-click runner works: `./scripts/colossus/run.sh configs/default.yaml`
- [ ] Auto-detection runs (GPU, storage)
- [ ] Config generation works
- [ ] Validation passes
- [ ] Benchmark executes

### Hardware Auto-Config
- [ ] Auto-config generates config: `bench colossus auto-config`
- [ ] Generated config is valid
- [ ] Recommendations match hardware
- [ ] Can run with generated config

### Version Pinning
- [ ] Pin script works: `./scripts/colossus/pin_versions.sh`
- [ ] NIM digest captured
- [ ] OpenFold commit captured
- [ ] Requirements frozen
- [ ] Can use pins in config

### Campaign Mode (Optional)
- [ ] Can create campaign: `bench colossus campaign-create campaigns/test`
- [ ] Can add run to campaign
- [ ] Can aggregate campaign results
- [ ] Can generate campaign report

## Performance Validation

### Storage Configuration
- [ ] FAST_WORKDIR points to fast storage (/mnt/primary on Colossus)
- [ ] PERSIST_DIR points to persistent storage (home or volume)
- [ ] Sufficient space on both paths (100GB+)
- [ ] Write permissions on both paths

### GPU Configuration
- [ ] GPU is visible: `nvidia-smi`
- [ ] No other processes using GPU
- [ ] CUDA_VISIBLE_DEVICES unset (or includes desired GPU)

### Network Configuration
- [ ] Can reach NGC registry: `docker pull nvcr.io/nim/openfold/openfold2:latest`
- [ ] NIM container pulled successfully
- [ ] No proxy/firewall blocking Docker

## Documentation

- [ ] Read COLOSSUS_DEPLOY.md
- [ ] Read docs/COLOSSUS_QUICKSTART.md
- [ ] Understand available configurations
- [ ] Know where to find results
- [ ] Know how to analyze results

## Post-Deployment

### First Production Run
- [ ] Selected appropriate config (default, casp15, etc.)
- [ ] Estimated runtime acceptable
- [ ] Started benchmark
- [ ] Monitoring progress
- [ ] Results being written

### Result Verification
- [ ] Benchmark completed without errors
- [ ] Records generated (check record count)
- [ ] Analysis ran successfully
- [ ] HTML report viewable
- [ ] Metrics look reasonable

### Troubleshooting Preparation
- [ ] Know where logs are (benchmark.log in results dir)
- [ ] Know how to check GPU usage (nvidia-smi)
- [ ] Know how to check disk space (df -h)
- [ ] Have COLOSSUS_DEPLOY.md troubleshooting section handy

## Advanced Features (Optional)

### Multi-GPU Campaign
- [ ] Campaign directory created
- [ ] Runs added from multiple GPUs
- [ ] Aggregation completed
- [ ] Comparison report generated

### Checkpointing (When Implemented)
- [ ] Can start with checkpointing
- [ ] Can resume from checkpoint
- [ ] No duplicate work after resume

### Git Sync (Optional)
- [ ] Git repository initialized
- [ ] Can enable Git sync
- [ ] Checkpoints being committed
- [ ] Results pushed to remote

## Final Verification

Run comprehensive deployment test: `./scripts/colossus/test_deployment.sh`

- [ ] All phases pass
- [ ] Smoke test completes (if ran)
- [ ] Analysis generation works
- [ ] HTML report created

## Sign-Off

- [ ] All critical items checked
- [ ] Smoke test passed
- [ ] Ready for production benchmarks

**Date:** ________________

**Tester:** ________________

**GPU Type:** ________________

**Notes:**

_____________________________________________

_____________________________________________

_____________________________________________

---

## Quick Reference Commands

```bash
# Bootstrap
./scripts/colossus/bootstrap.sh
source .env.colossus

# Validate
./scripts/colossus/validate.sh

# Smoke test
bench run --config configs/smoke_test.yaml

# Full deployment test
./scripts/colossus/test_deployment.sh

# Hardware detection
bench colossus detect

# Auto-config
bench colossus auto-config

# One-click run
./scripts/colossus/run.sh

# Production benchmark
bench run --config configs/casp15.yaml

# Analyze results
bench analyze results/latest
```

---

## Common Issues and Fixes

| Issue | Check | Fix |
|-------|-------|-----|
| NGC_API_KEY error | `echo $NGC_API_KEY` | `export NGC_API_KEY="..."` |
| Docker daemon error | `docker ps` | `sudo systemctl start docker` |
| bench not found | `which bench` | `source .env.colossus; pip install -e .` |
| Import errors | `python3 -c "import pydantic"` | `pip install -e .` |
| CUDA OOM | `nvidia-smi` | Reduce MSA depth or use single model |
| Slow I/O | `echo $FAST_WORKDIR` | Should be /mnt/primary, not home |

---

## Success Metrics

A successful deployment should show:

- ✅ Validation: 25+ tests passed, 0 critical failures
- ✅ Smoke test: 2 records in ~2 minutes
- ✅ Default benchmark: ~10 records in ~30 minutes
- ✅ CASP15 benchmark: ~36 records in ~3-4 hours
- ✅ Analysis: HTML report with plots and tables
- ✅ Performance: GPU >80% utilized during inference

---

## Support

If any checklist items fail:

1. Check error messages carefully
2. Review COLOSSUS_DEPLOY.md troubleshooting section
3. Run `./scripts/colossus/test_deployment.sh` for diagnostics
4. Check logs: results/*/benchmark.log
5. Verify hardware: `nvidia-smi`, `df -h`

Documentation:
- [COLOSSUS_DEPLOY.md](COLOSSUS_DEPLOY.md) - Deployment guide
- [docs/COLOSSUS_QUICKSTART.md](docs/COLOSSUS_QUICKSTART.md) - User guide
- [docs/IMPLEMENTATION_SUMMARY.md](docs/IMPLEMENTATION_SUMMARY.md) - Technical details
