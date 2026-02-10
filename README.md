# OpenFold2-NIM Performance Benchmark

Production-ready benchmarking suite comparing NVIDIA OpenFold2 NIM microservice against open-source OpenFold.

## Features

- **Out-of-the-box execution**: Clone → bootstrap → run benchmarks → view HTML report
- **Comprehensive metrics**: Latency, GPU utilization, memory, energy, accuracy (RMSD, lDDT)
- **Pareto frontier analysis**: Find optimal accuracy/performance trade-offs
- **Multi-GPU support**: Run on A100, H100, or other GPUs
- **Colossus-optimized**: Scripts and docs for NVIDIA Colossus infrastructure

## Quick Start

### Prerequisites

- NVIDIA GPU with drivers
- Docker with nvidia-container-toolkit
- NGC API key (for NIM): https://catalog.ngc.nvidia.com/
- Python 3.10+
- 100 GB free disk space

### Installation

```bash
git clone https://github.com/your-org/openfold2-bench.git
cd openfold2-bench

# Install dependencies with pip
pip install -e .

# Set NGC API key
export NGC_API_KEY="your_key_here"
```

### Running on Colossus

```bash
# Bootstrap Colossus environment
./scripts/bootstrap_colossus.sh

# Source environment variables
source .env.colossus

# Run full benchmark
./scripts/run_all.sh

# Results will be at: results/run_*/analysis/report.html
```

### Running Locally

```bash
# Preflight checks
bench preflight

# Run default benchmark (~1-2 hours)
bench run --config configs/default.yaml

# View results
open results/run_*/analysis/report.html
```

## Configuration

See `configs/` for examples:
- `default.yaml`: Fast benchmark with accuracy evaluation (~1-2 hours)
- `full_matrix.yaml`: Comprehensive with scaling studies (~8-12 hours)

### Example Configuration

```yaml
gpu:
  device_ids: [0]
  sampling_interval_ms: 50

nim:
  enabled: true
  container_image: "nvcr.io/nim/openfold/openfold2:latest"
  cache_dir: "${FAST_CACHE:-$HOME}/nim_cache"
  backend: "tensorrt"
  model_sets:
    - [3]              # Single model
    - [1, 2, 3, 4, 5]  # Ensemble

suites:
  - name: accuracy_small
    targets_file: bench/dataset/targets.yaml
    msa_depth: 1
    repeats: 3
```

## CLI Reference

```bash
# Validate environment
bench preflight

# Prepare datasets
bench prepare-data --config configs/default.yaml

# Run benchmark
bench run --config configs/default.yaml --output-dir results/run_001

# Generate analysis
bench analyze results/run_001

# Aggregate multi-machine results
bench aggregate results/*/manifest.json --output-dir results/aggregate
```

## Results Schema

Each benchmark run produces:
- `manifest.json`: Run metadata and environment info
- `records.parquet`: Per-prediction metrics (fast analysis)
- `records.jsonl`: Human-readable metrics
- `timeseries/*.parquet`: GPU/CPU monitoring data
- `structures/`: Predicted protein structures
- `analysis/report.html`: Interactive HTML report with plots

## Key Metrics

### Performance
- **Wall time**: End-to-end latency per prediction
- **GPU hours**: Normalized compute cost
- **Time-to-first-GPU**: Startup/overhead latency
- **GPU utilization**: SM and memory utilization
- **Energy**: Power consumption (Wh)

### Accuracy
- **Cα RMSD**: Coordinate accuracy after Kabsch alignment
- **Cα lDDT**: Local distance difference test (0-1 scale)
- **Mean pLDDT**: Model confidence (0-100)

## Documentation

- [Colossus Runbook](docs/COLOSSUS_RUNBOOK.md): Operations guide for Colossus
- [Methodology](docs/METHODOLOGY.md): Benchmarking methodology and fairness
- [Metrics Schema](docs/METRICS_SCHEMA.md): Complete metrics documentation
- [API Integration](docs/API_INTEGRATION.md): NIM and OpenFold integration details

## Example Output

The benchmark generates:
1. **Pareto frontier plot**: Accuracy vs performance trade-offs
2. **Scaling analysis**: Sequence length and MSA depth scaling
3. **GPU utilization**: Distribution and time-series plots
4. **Per-target accuracy**: Detailed breakdown by protein
5. **Energy efficiency**: Power consumption analysis

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black bench/
ruff check bench/

# Type checking
mypy bench/
```

## Troubleshooting

### NIM Container Won't Start
- Check NGC_API_KEY is set: `echo $NGC_API_KEY`
- Check port 8000 is available: `lsof -i :8000`
- Check GPU access: `docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu20.04 nvidia-smi`

### Out of Disk Space
- Clean old results: `rm -rf results/run_*` (after backing up)
- Clean Docker: `docker system prune -a`

### Slow Performance
- Ensure using fast storage (primary drive on Colossus, not volume)
- Check GPU not throttling: `nvidia-smi dmon -s puct`

## License

MIT License - see LICENSE file

## Citation

If you use this benchmark in your research, please cite:

```bibtex
@software{openfold2_nim_bench,
  title={OpenFold2-NIM Performance Benchmark},
  author={NVIDIA Performance Team},
  year={2025},
  url={https://github.com/your-org/openfold2-bench}
}
```

## Contributing

Contributions welcome! Please open an issue or pull request.

## Support

For questions or issues:
- GitHub Issues: https://github.com/your-org/openfold2-bench/issues
- NVIDIA Developer Forums: https://forums.developer.nvidia.com/
