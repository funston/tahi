# DGX Training Runbook: SchemaSQLCoprocessor-7B

This document is a step-by-step guide for training a small specialist SQL generator coprocessor on the DGX. The goal is not to replace a foundation model but to train a **component** that plugs into OCTO.

## What we are training

**Model:** `SchemaSQLCoprocessor-7B`  
**Base model:** `Qwen/Qwen2.5-Coder-7B-Instruct`  
**Method:** LoRA fine-tuning (fits in 128GB GPU RAM)  
**Input:** OCTO grounding packet (schema + question + evidence + constraints)  
**Output:** SQLite SQL  
**Why:** A local 7B specialist is cheaper and faster than Claude per query, and it consumes OCTO's structured grounding rather than raw text.

## Hardware assumptions

- DGX with at least one 128GB GPU (e.g., A100 80GB x2, or H100 80GB x2, or A100 40GB x4)
- CUDA 12.x
- Internet access to download models and datasets
- ~200GB free disk space for model checkpoints and data

## Phase 1: DGX Environment Setup

### 1.1 SSH into the DGX

```bash
ssh your-user@dgx-hostname
```

### 1.2 Create a project directory

```bash
export OCTO_DGX_ROOT=/raid/your-user/octo-dgx
mkdir -p $OCTO_DGX_ROOT/{data,models,logs,scripts}
cd $OCTO_DGX_ROOT
```

### 1.3 Create a Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

### 1.4 Install PyTorch with CUDA

Check CUDA version first:

```bash
nvidia-smi
nvcc --version
```

Install matching PyTorch. For CUDA 12.1:

```bash
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121
```

Verify GPU access:

```bash
python - <<'PY'
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU count: {torch.cuda.device_count()}")
for i in range(torch.cuda.device_count()):
    print(f"  GPU {i}: {torch.cuda.get_device_name(i)} {torch.cuda.get_device_properties(i).total_memory / 1e9:.1f} GB")
PY
```

### 1.5 Install training dependencies

```bash
pip install transformers==4.46.3
pip install datasets==3.1.0
pip install accelerate==1.1.1
pip install peft==0.14.0
pip install trl==0.12.0
pip install bitsandbytes==0.45.0
pip install wandb
pip install sqlglot
pip install sentencepiece
pip install protobuf
```

### 1.6 Log in to Hugging Face and Weights & Biases

```bash
huggingface-cli login
wandb login
```

## Phase 2: Prepare Training Data

### 2.1 Copy OCTO repo or use a stripped-down data builder

You need the BIRD training data formatted as grounded packets. The easiest path is to run the data builder on a machine with the OCTO repo checked out, then copy the resulting JSONL to the DGX.

On the DGX:

```bash
# Clone OCTO repo (or rsync from your laptop)
git clone git@github.com:your-org/octo.git $OCTO_DGX_ROOT/octo
cd $OCTO_DGX_ROOT/octo
```

### 2.2 Build the training dataset

Run the data preparation script:

```bash
source $OCTO_DGX_ROOT/.venv/bin/activate
export PYTHONPATH=$OCTO_DGX_ROOT/octo/src:$OCTO_DGX_ROOT/octo
python scripts/prepare_schema_sql_training_data.py \
  --output $OCTO_DGX_ROOT/data/schema_sql_train.jsonl \
  --split train \
  --hf-repo-id Sudnya/bird-sql \
  --hf-cache-dir $OCTO_DGX_ROOT/data/hf_cache
```

This produces one JSON line per example:

```json
{
  "instruction": "You are writing SQLite SQL for the BIRD benchmark...",
  "input": "Database: financial\nSchema:\nTABLE district (...)\n...\nQuestion: What is the average salary in Prague?\nEvidence: ...",
  "output": "SELECT AVG(A11) FROM district WHERE A2 = 'Praha'"
}
```

### 2.3 Verify the dataset

```bash
wc -l $OCTO_DGX_ROOT/data/schema_sql_train.jsonl
head -1 $OCTO_DGX_ROOT/data/schema_sql_train.jsonl | python -m json.tool
```

## Phase 3: Training

### 3.1 Review the training script

Open `scripts/train_schema_sql_coprocessor.py` and confirm:

- `BASE_MODEL` is set to `Qwen/Qwen2.5-Coder-7B-Instruct`
- `OUTPUT_DIR` points to `$OCTO_DGX_ROOT/models/schema_sql_coprocessor_7b`
- LoRA rank and batch size fit your GPU memory

### 3.2 Start training

```bash
source $OCTO_DGX_ROOT/.venv/bin/activate
export PYTHONPATH=$OCTO_DGX_ROOT/octo/src:$OCTO_DGX_ROOT/octo
export WANDB_PROJECT=octo-schema-sql-coprocessor

cd $OCTO_DGX_ROOT
python octo/scripts/train_schema_sql_coprocessor.py \
  --data_path $OCTO_DGX_ROOT/data/schema_sql_train.jsonl \
  --output_dir $OCTO_DGX_ROOT/models/schema_sql_coprocessor_7b \
  --num_epochs 3 \
  --batch_size 4 \
  --gradient_accumulation_steps 4 \
  --lora_r 64 \
  --lora_alpha 128 \
  --learning_rate 2e-4 \
  --max_seq_length 2048
```

Expected behavior:

- Model downloads (~15GB).
- Dataset tokenizes.
- Training runs for 3 epochs.
- Checkpoints save every 500 steps.
- Final merged model saves to `$OUTPUT_DIR/final_merged`.

### 3.3 Monitor training

In another terminal:

```bash
tail -f $OCTO_DGX_ROOT/logs/train.log
```

Or watch Weights & Biases dashboard.

### 3.4 Expected runtime

With one A100 80GB and ~9,000 BIRD train examples:

- ~4–6 hours for 3 epochs at batch size 4.
- Multi-GPU via Accelerate can cut this in half.

## Phase 4: Convert to OCTO Coprocessor

### 4.1 Update the coprocessor wrapper

After training, the model lives at:

```
$OCTO_DGX_ROOT/models/schema_sql_coprocessor_7b/final_merged
```

Copy or symlink it into the OCTO repo:

```bash
mkdir -p $OCTO_DGX_ROOT/octo/models
ln -s $OCTO_DGX_ROOT/models/schema_sql_coprocessor_7b/final_merged \
  $OCTO_DGX_ROOT/octo/models/schema_sql_coprocessor_7b
```

### 4.2 Load it as a coprocessor

Use the existing `TrainedSQLGeneratorCoprocessor` wrapper (see `implementations/bird/sql_generator_coprocessor.py`) or create one that loads the local model.

Example usage:

```python
from implementations.bird import (
    BirdExecutionAdapter,
    TrainedSQLGeneratorCoprocessor,
)

coprocessor = TrainedSQLGeneratorCoprocessor(
    model_path="models/schema_sql_coprocessor_7b",
    device="cuda",
)

adapter = BirdExecutionAdapter(
    snapshots_by_db=snapshots,
    db_paths_by_db=db_paths,
    grounding_adapter=grounding_adapter,
    sql_coprocessors=[coprocessor],
    use_repair=True,
    max_candidates=4,
)
```

## Phase 5: Evaluate on BIRD

### 5.1 Run BIRD execution benchmark

```bash
python examples/run_octo_bird_execution_benchmark.py \
  --source huggingface \
  --sql-backend trained \
  --trained-model-path $OCTO_DGX_ROOT/octo/models/schema_sql_coprocessor_7b \
  --max-candidates 4 \
  --use-repair \
  --output benchmarks/bird/execution_full_dev_trained_7b.json
```

### 5.2 Compare against Claude baseline

```bash
python examples/render_bird_benchmark_report.py \
  --reports \
    benchmarks/bird/execution_100_claude_sonnet4.json \
    benchmarks/bird/execution_full_dev_trained_7b.json \
  --output benchmarks/bird/comparison_trained_vs_claude.html
```

## Phase 6: Optional — Multi-GPU and Larger Models

### 6.1 Multi-GPU training

Use Accelerate:

```bash
accelerate launch --multi_gpu --num_processes 2 \
  octo/scripts/train_schema_sql_coprocessor.py \
  --data_path ... \
  --output_dir ... \
  --batch_size 4
```

### 6.2 Larger models

With 128GB GPU RAM:

- **7B:** full fine-tuning possible, but LoRA is safer.
- **13B:** LoRA recommended.
- **32B:** QLoRA (4-bit) required.

Set `load_in_4bit=True` in the training script for 32B models.

## Safety checklist

- [ ] DGX has CUDA 12.x and matching PyTorch.
- [ ] `nvidia-smi` shows GPUs.
- [ ] Hugging Face token has access to base model.
- [ ] Training data JSONL exists and is non-empty.
- [ ] Output directory has disk space.
- [ ] Weights & Biases is logged in.
- [ ] Test training on 100 examples first to verify the script runs.

## Commands summary

```bash
# Setup
export OCTO_DGX_ROOT=/raid/your-user/octo-dgx
python3 -m venv $OCTO_DGX_ROOT/.venv
source $OCTO_DGX_ROOT/.venv/bin/activate
pip install -r octo/requirements-train.txt

# Data
python scripts/prepare_schema_sql_training_data.py --output $OCTO_DGX_ROOT/data/schema_sql_train.jsonl

# Train
python scripts/train_schema_sql_coprocessor.py \
  --data_path $OCTO_DGX_ROOT/data/schema_sql_train.jsonl \
  --output_dir $OCTO_DGX_ROOT/models/schema_sql_coprocessor_7b \
  --num_epochs 3

# Evaluate
python examples/run_octo_bird_execution_benchmark.py \
  --sql-backend trained \
  --trained-model-path $OCTO_DGX_ROOT/models/schema_sql_coprocessor_7b/final_merged \
  --max-candidates 4 --use-repair \
  --output benchmarks/bird/execution_full_dev_trained_7b.json
```

## Notes for future Kimi runs

When this runbook is handed back to Kimi, the next concrete steps are:

1. Verify the DGX environment (CUDA, PyTorch, GPUs).
2. Run the data preparation script. If it fails, fix paths or HF access.
3. Run a 100-example smoke test of the training script.
4. Run full training.
5. Convert the saved model to an OCTO coprocessor wrapper.
6. Run BIRD execution benchmark and compare to Claude baseline.
