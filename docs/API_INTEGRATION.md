# API Integration Guide

This document details how the benchmark suite integrates with NIM and OpenFold APIs, including payload formats, endpoint specifications, and configuration options.

## Table of Contents

- [NIM Integration](#nim-integration)
  - [Container Configuration](#container-configuration)
  - [API Endpoints](#api-endpoints)
  - [Payload Format](#payload-format)
  - [Response Format](#response-format)
  - [Backend Selection](#backend-selection)
- [OpenFold Integration](#openfold-integration)
  - [CLI Interface](#cli-interface)
  - [Alignment Directory Structure](#alignment-directory-structure)
  - [Model Presets](#model-presets)
  - [Weights Configuration](#weights-configuration)
- [Precomputed MSA Integration](#precomputed-msa-integration)

---

## NIM Integration

### Container Configuration

The NIM (NVIDIA Inference Microservice) runs as a Docker container with the following configuration:

#### Environment Variables

**Required:**
- `NGC_API_KEY`: NVIDIA NGC API key for container authentication
  - Obtain from: https://ngc.nvidia.com/setup/api-key
  - Set in environment: `export NGC_API_KEY=your_key_here`

**Optional:**
- `NIM_OPENFOLD_BACKEND`: Backend selection ("tensorrt" or "torch")
  - Default: "tensorrt"
  - Override in config: `nim.backend`

#### Container Launch Parameters

```python
docker run \
  --gpus '"device=0"' \                    # GPU device specification
  --shm-size=2g \                          # Shared memory size
  -e NGC_API_KEY=$NGC_API_KEY \            # NGC authentication
  -e NIM_OPENFOLD_BACKEND=tensorrt \       # Backend selection
  -v /path/to/cache:/opt/nim/.cache \      # Model cache mount
  -p 8000:8000 \                           # Port mapping
  nvcr.io/nim/openfold/openfold2:1.0       # Container image
```

**Key Parameters:**
- `--gpus`: GPU device specification
  - Single GPU: `'"device=0"'`
  - Multiple GPUs: `'"device=0,1,2,3"'`
  - All GPUs: `'all'`
- `--shm-size`: Shared memory size (minimum 2GB recommended)
- `-v`: Volume mount for model cache (persistent across restarts)
- `-p`: Port mapping (default: 8000 for HTTP API)

#### Container Lifecycle

1. **Pull Image:**
   ```bash
   docker pull nvcr.io/nim/openfold/openfold2:1.0
   ```

2. **Start Container:**
   - Benchmark suite automatically starts container if `nim.base_url` is `null`
   - Startup time: ~10-60 seconds depending on cache state

3. **Health Check:**
   - Endpoint: `GET /health`
   - Expected response: `{"status": "ready"}`
   - Benchmark suite polls until ready

4. **Metadata Retrieval:**
   - Endpoint: `GET /v1/metadata`
   - Returns version, backend, model information

5. **Shutdown:**
   - Automatic cleanup after benchmark completion
   - Manual: `docker stop <container_name>`

---

### API Endpoints

#### Base URL

- **Local container:** `http://localhost:8000`
- **Remote service:** Configured via `nim.base_url` in config

#### Health Endpoint

```
GET /health
```

**Response:**
```json
{
  "status": "ready"
}
```

#### Metadata Endpoint

```
GET /v1/metadata
```

**Response:**
```json
{
  "version": "1.0.0",
  "backend": "tensorrt",
  "models_available": [1, 2, 3, 4, 5],
  "container_digest": "sha256:abc123...",
  "build_date": "2024-01-15"
}
```

#### Prediction Endpoint

```
POST /v1/predict
Content-Type: application/json
```

---

### Payload Format

The prediction request payload follows this schema:

```json
{
  "sequence": "MKTAYIAKQRQISFVKSHFSRQLE...",
  "msa": {
    "format": "a3m",
    "content": ">query\nMKTAYIAKQRQISFVKSHFSRQLEMKTAYI...\n>homolog_1\nMKAAYIAKQRQISFVKSHFSRQLEMKTAYI...\n"
  },
  "models": [3],
  "return_representations": false,
  "return_timings": false
}
```

#### Field Descriptions

**`sequence`** (string, required)
- Amino acid sequence using standard 20-letter code
- Valid characters: `ACDEFGHIKLMNPQRSTVWY`
- Length: Typically 50-2700 amino acids
- Example: `"MKTAYIAKQRQISFVKSHFSRQLE"`

**`msa`** (object, required)
- **`format`**: MSA format ("a3m" only for NIM)
- **`content`**: MSA content as string
  - A3M format: FASTA-like with `>header\nsequence` entries
  - First entry must be query sequence
  - Subsequent entries are homologs

**`models`** (array of integers, required)
- AlphaFold parameter sets to use
- Valid values: `[1]`, `[2]`, `[3]`, `[4]`, `[5]`, or combinations
- Common configurations:
  - Single model: `[3]` (fastest, good accuracy)
  - Ensemble: `[1, 2, 3, 4, 5]` (highest accuracy, 5x slower)
- NIM uses AlphaFold v2.3.0 weights

**`return_representations`** (boolean, optional)
- If `true`, returns intermediate model representations
- Default: `false`
- Note: Increases response size and latency

**`return_timings`** (boolean, optional)
- If `true`, returns internal timing breakdown
- Default: `false`
- Useful for profiling NIM internals

---

### Response Format

**Success Response (200 OK):**

```json
{
  "structure": {
    "format": "pdb",
    "content": "ATOM      1  N   MET A   1      10.123  20.456  30.789...\n"
  },
  "confidence": {
    "plddt": [89.2, 91.5, 88.3, ...],
    "mean_plddt": 89.7
  },
  "metadata": {
    "models_used": [3],
    "msa_depth": 128,
    "sequence_length": 234,
    "backend": "tensorrt"
  }
}
```

#### Response Fields

**`structure`**
- **`format`**: "pdb"
- **`content`**: PDB format structure as string
  - Contains ATOM records for all atoms
  - B-factor column contains per-residue pLDDT scores

**`confidence`**
- **`plddt`**: Array of per-residue pLDDT scores (0-100)
- **`mean_plddt`**: Mean pLDDT across all residues

**`metadata`**
- **`models_used`**: Models that were run
- **`msa_depth`**: Number of MSA sequences processed
- **`sequence_length`**: Length of input sequence
- **`backend`**: Backend used ("tensorrt" or "torch")

**Error Response (4xx/5xx):**

```json
{
  "error": {
    "code": "INVALID_SEQUENCE",
    "message": "Sequence contains invalid character: 'X'"
  }
}
```

---

### Backend Selection

NIM supports two inference backends:

#### TensorRT Backend (Default)

**Configuration:**
```yaml
nim:
  backend: "tensorrt"
```

**Environment Variable:**
```bash
export NIM_OPENFOLD_BACKEND=tensorrt
```

**Characteristics:**
- **Performance:** Fastest (3-5x speedup vs Torch)
- **Precision:** FP16 (mixed precision)
- **Compilation:** First run compiles TensorRT engines (cached)
- **GPU Support:** Requires NVIDIA GPU with TensorRT support
- **Use Case:** Production deployments, benchmarking

**First-Run Behavior:**
- Compiles optimized engines for specific GPU architecture
- Compilation time: ~5-10 minutes (one-time, cached)
- Subsequent runs use cached engines

#### Torch Backend

**Configuration:**
```yaml
nim:
  backend: "torch"
```

**Environment Variable:**
```bash
export NIM_OPENFOLD_BACKEND=torch
```

**Characteristics:**
- **Performance:** Slower than TensorRT (baseline)
- **Precision:** BF16 (configurable)
- **Compilation:** No ahead-of-time compilation
- **GPU Support:** Any GPU with PyTorch support
- **Use Case:** Debugging, algorithm development, CPU inference

**Comparison:**

| Aspect | TensorRT | Torch |
|--------|----------|-------|
| Speed | 3-5x faster | Baseline |
| First Run | Slow (compilation) | Normal |
| Subsequent Runs | Fast (cached) | Normal |
| Accuracy | Identical | Identical |
| Precision | FP16 | BF16 |

---

## OpenFold Integration

### CLI Interface

OpenFold is invoked via command-line interface:

```bash
python /path/to/openfold/run_pretrained_openfold.py \
  /path/to/fasta \                    # Input FASTA file
  /path/to/template_mmcif \           # Template database (unused)
  --output_dir /path/to/output \      # Output directory
  --model_device cuda:0 \             # GPU device
  --config_preset model_3_ptm \       # Model preset
  --use_precomputed_alignments /path/to/alignments \  # Alignment dir
  --bf16 \                            # BF16 precision
  --save_outputs                      # Save PDB output
```

#### Required Arguments

- **Input FASTA:** Single-sequence FASTA file
  ```
  >target_id
  MKTAYIAKQRQISFVKSHFSRQLE...
  ```

- **Template database path:** Required but unused (templates disabled)
  - Can point to empty directory
  - Not used when `--use_precomputed_alignments` is set

- **Output directory:** Where PDB and confidence scores are written

#### Key Options

**`--config_preset`**
- Model configuration preset
- Valid values: See [Model Presets](#model-presets) section
- Default: `model_1_ptm`

**`--model_device`**
- GPU device specification
- Format: `cuda:0` (single GPU) or `cuda:0,1,2,3` (multi-GPU)

**`--use_precomputed_alignments`**
- Path to directory containing precomputed alignments
- If set, skips MSA search
- See [Alignment Directory Structure](#alignment-directory-structure)

**`--bf16`**
- Enable BF16 (bfloat16) mixed precision
- Reduces memory usage, minimal accuracy impact
- Recommended for benchmarking to match NIM precision

**`--save_outputs`**
- Save PDB structure and confidence scores
- Required for accuracy evaluation

---

### Alignment Directory Structure

When using `--use_precomputed_alignments`, OpenFold expects this directory structure:

```
alignment_dir/
  bfd_uniclust_hits.a3m          # Main MSA (BFD + UniClust)
  uniref90_hits.sto              # UniRef90 hits (Stockholm format)
  mgnify_hits.sto                # MGnify environmental hits
  pdb70_hits.hhr                 # Template search results (HHsearch format)
```

#### File Descriptions

**`bfd_uniclust_hits.a3m`** (required)
- Primary MSA in A3M format
- Combines BFD and UniClust30 database hits
- Most important for prediction accuracy
- Format: Same as NIM MSA input

**`uniref90_hits.sto`** (required)
- UniRef90 database hits in Stockholm format
- Used for MSA clustering and sampling
- Format: Stockholm 1.0

**`mgnify_hits.sto`** (optional)
- Environmental sequences from MGnify database
- Adds sequence diversity
- Format: Stockholm 1.0

**`pdb70_hits.hhr`** (required)
- Template search results from HHsearch against PDB70
- For no-template mode, use empty/minimal HHR:
  ```
  Query         query
  Match_columns 0
  No_of_seqs    1
  Done!
  ```

#### Format Notes

**A3M Format:**
```
>query
MKTAYIAKQRQISFVKSHFSRQLE
>homolog_1
MKTAAIIAKQRQISFVKSHFSRQLE
>homolog_2
MKTAYIAKQRQIAFVKSHFSRQLE
```

**Stockholm Format:**
```
# STOCKHOLM 1.0
query              MKTAYIAKQRQISFVKSHFSRQLE
homolog_1          MKTAAIIAKQRQISFVKSHFSRQLE
homolog_2          MKTAYIAKQRQIAFVKSHFSRQLE
//
```

---

### Model Presets

OpenFold supports multiple model configurations via `--config_preset`:

#### Available Presets

**`model_1_ptm`**, **`model_2_ptm`**, **`model_3_ptm`**, **`model_4_ptm`**, **`model_5_ptm`**
- Single AlphaFold parameter set with pTM (predicted TM-score) head
- Fastest inference
- Recommended: `model_3_ptm` (good balance of speed/accuracy)

**`model_1`**, **`model_2`**, **`model_3`**, **`model_4`**, **`model_5`**
- Single parameter set without pTM head
- Slightly faster than PTM variants
- No inter-domain confidence estimates

**`finetuning_ptm`**, **`finetuning_no_ptm`**
- Fine-tuned models for specific use cases
- Not recommended for benchmarking

#### Preset Comparison

| Preset | pTM Head | Speed | Use Case |
|--------|----------|-------|----------|
| `model_3_ptm` | Yes | Fast | Recommended for benchmarking |
| `model_3` | No | Fastest | Speed-critical applications |
| All 5 models | - | 5x slower | Maximum accuracy ensemble |

---

### Weights Configuration

Control model weight source for apples-to-apples comparison with NIM:

```yaml
openfold:
  weights_source: "alphafold_official"  # or "openfold"
  weights_path: /custom/path/to/weights  # optional override
```

#### Weights Sources

**`"openfold"`** (default)
- OpenFold-trained weights
- May differ slightly from AlphaFold official
- Use for OpenFold-specific evaluation

**`"alphafold_official"`**
- AlphaFold v2.3.0 official weights from DeepMind
- **Recommended for NIM comparison** (NIM uses these weights)
- Ensures model parameter parity

**Custom Path:**
- Set `weights_path` to use custom checkpoint
- Must be compatible with OpenFold architecture
- Use for fine-tuned models or custom training

#### Obtaining AlphaFold Weights

```bash
# Download AlphaFold v2.3.0 parameters
wget https://storage.googleapis.com/alphafold/alphafold_params_2022-12-06.tar
tar -xf alphafold_params_2022-12-06.tar -C /path/to/weights
```

---

## Precomputed MSA Integration

### Motivation

By default, NIM and OpenFold generate MSAs independently, making the benchmark measure MSA pipeline differences rather than pure inference performance. Precomputed MSAs solve this:

**Benefits:**
- Identical inputs for both systems
- Reproducible across runs
- Faster benchmarking (skip MSA generation)
- Isolates inference performance

### Configuration

```yaml
suites:
  - name: inference_only
    precomputed_msa_dir: "data/precomputed/casp15_msa128"
    inference_only_mode: true
```

### Directory Structure

```
precomputed_msa_dir/
  {target_id}/
    manifest.json                  # Metadata and hashes
    nim_msa.a3m                   # NIM MSA input
    openfold_alignments/          # OpenFold alignment directory
      bfd_uniclust_hits.a3m       # (identical to nim_msa.a3m)
      uniref90_hits.sto
      mgnify_hits.sto
      pdb70_hits.hhr
```

### Manifest Format

```json
{
  "target_id": "T1234",
  "sequence": "MKTAYIAKQRQISFVKSHFSRQLE...",
  "msa_depth": 128,
  "msa_hash": "a3f2e8b4c9d7f1a2b5e6d8c4...",
  "template_hash": null,
  "nim_a3m_path": "T1234/nim_msa.a3m",
  "openfold_alignment_dir": "T1234/openfold_alignments",
  "template_dir": null,
  "created_at": "2026-02-10T14:30:22Z",
  "source": "synthetic"
}
```

### Verification

The benchmark suite automatically verifies MSA integrity:
1. Checks manifest exists
2. Verifies all files exist
3. Computes SHA256 hash of MSA content
4. Compares to manifest hash
5. Fails if mismatch detected

This ensures data integrity and reproducibility.

### Generating Precomputed MSAs

Use the provided CLI tool:

```bash
python scripts/precompute_msas.py \
  --targets bench/dataset/casp15_targets.yaml \
  --output data/precomputed/casp15_msa128 \
  --msa-depth 128
```

---

## Error Handling

### Common Errors

**NIM:**
- `NGC_API_KEY not set`: Set environment variable
- `Container failed to start`: Check GPU availability, shared memory
- `Timeout waiting for /health`: Container startup issue, check logs
- `Invalid sequence`: Check for non-standard amino acids

**OpenFold:**
- `CUDA out of memory`: Reduce batch size or use smaller model
- `Alignment directory not found`: Check `use_precomputed_alignments` path
- `Template database required`: Provide path (even if unused)

### Debugging

**NIM Container Logs:**
```bash
docker logs <container_name>
```

**OpenFold Verbose Output:**
```bash
# Add to OpenFold command
--verbose
```

---

## Performance Tips

1. **Use TensorRT backend** for NIM (default)
2. **Enable BF16** for OpenFold (`--bf16` flag)
3. **Precompute MSAs** for faster iteration
4. **Pin versions** with digest hashes
5. **Use model_3_ptm** for single-model benchmarks
6. **Warm up** before measurement passes

---

## Version Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| NIM Container | 1.0+ | Pin with digest |
| OpenFold | Latest main | Specify commit hash |
| AlphaFold Weights | v2.3.0 | Used by NIM |
| Docker | 20.10+ | Required for NIM |
| CUDA | 11.8+ | GPU driver requirement |

---

## References

- NIM Documentation: https://docs.nvidia.com/nim/
- OpenFold GitHub: https://github.com/aqlaboratory/openfold
- AlphaFold Paper: Jumper et al. (2021). *Nature*, 596:583-589
- AlphaFold Weights: https://github.com/deepmind/alphafold
