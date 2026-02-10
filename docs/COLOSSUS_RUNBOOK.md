# Colossus Operations Guide

## Storage Architecture on Colossus

### Images vs Volumes

- **Images**: Reinstalled locally each lease; changes are lost; best for deterministic testing
- **Volumes**: Persistent across leases but network-mounted; performance depends on network load

Reference: Colossus Introduction slides 10-30

### Storage Performance Hierarchy

Fastest to slowest:

1. **Primary drive** (local, non-persistent) - FASTEST
2. **Unix scratch/home** (persistent)
3. **NetApp file server** (persistent)
4. **Volume** (persistent, network-dependent)
5. **Secondary drive** (avoid)

Reference: Colossus Introduction slides 44-66

### Key Principle

**Local disk changes are lost after machine release.** Volumes persist and can be reattached to new machines.

Reference: Colossus User Guide pages 1-4

## Recommended Workflow

### Setup Phase

1. Lease machine with desired GPU (A100, H100)
2. Run bootstrap script:
   ```bash
   ./scripts/bootstrap_colossus.sh
   ```
   This script:
   - Verifies prerequisites (nvidia-smi, docker, nvidia-container-toolkit)
   - Creates cache directories on fastest disk (primary drive if available)
   - Pre-pulls NIM container to save time
   - Writes `.env.colossus` with optimal paths

3. Source environment variables:
   ```bash
   source .env.colossus
   ```

4. Install Python dependencies:
   ```bash
   pip install -e .
   ```

### Execution Phase

1. **Store working data on primary drive** for maximum performance:
   - NIM cache: `/mnt/primary/openfold_cache/nim_cache`
   - OpenFold repo: `/mnt/primary/openfold_cache/openfold_repo`
   - Intermediate results: `/mnt/primary/openfold_results`

2. **Run benchmark**:
   ```bash
   ./scripts/run_all.sh configs/default.yaml
   ```

   Or manually:
   ```bash
   bench run --config configs/default.yaml
   bench analyze results/run_*/
   ```

3. **Monitor progress**:
   ```bash
   # Watch GPU utilization
   watch -n 1 nvidia-smi

   # Follow logs
   tail -f results/run_*/bench.log
   ```

### Teardown Phase

1. **Copy final results to persistent storage**:
   ```bash
   cp -r results/run_* $PERSISTENT_VOLUME/openfold_results/
   ```

2. **Verify results were copied**:
   ```bash
   ls -lh $PERSISTENT_VOLUME/openfold_results/
   ```

3. **Clean up local disk** (optional, to free space):
   ```bash
   rm -rf /mnt/primary/openfold_cache
   rm -rf results/
   ```

4. **Release machine** via Colossus portal

### Multi-Machine Comparison

To compare results across different GPU types:

1. **Lease A100 machine** → run benchmark → copy results to volume:
   ```bash
   ./scripts/run_all.sh configs/default.yaml
   cp -r results/run_* $PERSISTENT_VOLUME/openfold_results/
   ```

2. **Lease H100 machine** → run benchmark → copy results to volume:
   ```bash
   ./scripts/run_all.sh configs/default.yaml
   cp -r results/run_* $PERSISTENT_VOLUME/openfold_results/
   ```

3. **On any machine**, aggregate results:
   ```bash
   bench aggregate $PERSISTENT_VOLUME/openfold_results/*/manifest.json \
     --output-dir $PERSISTENT_VOLUME/openfold_results/aggregate
   ```

## Disk Space Requirements

| Component | Size | Location |
|-----------|------|----------|
| NIM container | ~15-20 GB | Docker images |
| NIM runtime cache | ~30-50 GB | `$FAST_CACHE/nim_cache` |
| OpenFold repo + weights | ~10 GB | `$FAST_CACHE/openfold_repo` |
| Results per run | ~1-5 GB | `results/run_*` |
| **Total recommended** | **100 GB** | **Primary drive** |

## Performance Considerations

### Use Primary Drive for Caches

The bootstrap script automatically detects and uses the primary drive if available. If you manually configure paths:

```bash
# GOOD: Fast local storage
FAST_CACHE=/mnt/primary/openfold_cache

# BAD: Slow network storage
FAST_CACHE=$PERSISTENT_VOLUME/openfold_cache  # Will be much slower!
```

### Pre-pull Containers

Pre-pulling the NIM container saves 10-30 minutes on first run:

```bash
docker pull nvcr.io/nim/openfold/openfold2:latest
```

### Monitor GPU Throttling

If GPUs are thermal throttling, results will be misleading:

```bash
# Watch for throttling events
nvidia-smi dmon -s puct -c 100
```

If you see consistent low clocks or power limits, wait for GPUs to cool or request a different machine.

## Troubleshooting

### NIM Container Won't Start

**Check NGC_API_KEY**:
```bash
echo $NGC_API_KEY
# Should print your key, not empty
```

**Check port 8000 is available**:
```bash
lsof -i :8000
# Should show nothing if port is free
```

**Check GPU is visible to Docker**:
```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu20.04 nvidia-smi
# Should show GPU info
```

**Check Docker logs**:
```bash
docker logs openfold2-nim
```

### Out of Disk Space

**Clean up old results** (after copying to persistent storage):
```bash
rm -rf results/run_*
```

**Clean up Docker**:
```bash
docker system prune -a
# WARNING: This removes ALL unused containers, images, and volumes
```

**Check disk usage**:
```bash
df -h /mnt/primary
du -sh /mnt/primary/openfold_cache/*
```

### Slow Performance

**Verify using primary drive**:
```bash
echo $FAST_CACHE
# Should be /mnt/primary/... not $PERSISTENT_VOLUME/...
```

**Check GPU not being throttled**:
```bash
nvidia-smi dmon -s puct
# Watch Pwr (power) and SM (utilization) columns
```

**Check network not saturated** (if using volume):
```bash
iftop  # Monitor network usage
```

### Results Don't Persist After Release

This is expected! Local disk changes are lost. Always copy results to `$PERSISTENT_VOLUME` before releasing:

```bash
# Before releasing machine:
cp -r results/run_* $PERSISTENT_VOLUME/openfold_results/
```

### Container Pull Fails

If NGC container pull fails, check:

1. NGC_API_KEY is valid:
   ```bash
   docker login nvcr.io
   # Username: $oauthtoken
   # Password: $NGC_API_KEY
   ```

2. Network connectivity:
   ```bash
   ping nvcr.io
   ```

3. Try manual pull:
   ```bash
   docker pull nvcr.io/nim/openfold/openfold2:latest
   ```

## Best Practices

1. **Always use primary drive for caches** - 10-100x faster than volumes
2. **Copy results to persistent storage** before releasing machine
3. **Pre-pull containers** to save time on first run
4. **Monitor disk space** - benchmark needs 100+ GB
5. **Verify results copied** before releasing machine
6. **Use run IDs** to track multiple experiments
7. **Document configuration** in run manifest

## Quick Reference

```bash
# Bootstrap
./scripts/bootstrap_colossus.sh
source .env.colossus
pip install -e .

# Run
./scripts/run_all.sh configs/default.yaml

# Backup results
cp -r results/run_* $PERSISTENT_VOLUME/openfold_results/

# Aggregate
bench aggregate $PERSISTENT_VOLUME/openfold_results/*/manifest.json \
  --output-dir $PERSISTENT_VOLUME/openfold_results/aggregate

# Clean up
rm -rf /mnt/primary/openfold_cache
rm -rf results/
```
