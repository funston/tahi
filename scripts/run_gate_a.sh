#!/usr/bin/env bash
# Gate A -- symmetric oracle-memory ablation.
# Pre-registration: docs/OCTO_ENDGAME_PLAN.md section 2.
#
# Step 1 trains GCCA adapters on zero-noise gold-document memory.
# Step 2 scores the held-out split using the SAME memory bytes.
# The primary readout is max|tanh(alpha)| at the final epoch:
#   > 0.10  PASS    0.05-0.10  INCONCLUSIVE    < 0.05  FAIL (L3 is dead)

set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:."

MODEL="Qwen/Qwen2.5-1.5B-Instruct"
DATA="data/gcca_oracle"
CKPT="checkpoints/gcca_oracle"

echo "=== STEP 1: train on oracle memory ==="
.venv/bin/python scripts/train_gcca.py \
    --model "$MODEL" \
    --data "$DATA/train.jsonl" \
    --eval-data "$DATA/test.jsonl" \
    --memory-store "$DATA/memory_vectors.npz" \
    --epochs 15 \
    --output "$CKPT"

echo "=== STEP 2: evaluate on held-out ids ==="
.venv/bin/python benchmarks/run_l3_native.py \
    --model "$MODEL" \
    --checkpoint "$CKPT/gcca_epoch14.pt" \
    --questions data/enterprise_rag/questions.jsonl \
    --corpus data/enterprise_rag/sources \
    --memory-store "$DATA/memory_vectors.npz" \
    --question-ids-from "$DATA/test.jsonl" \
    --gnn off \
    --limit 139 \
    --output benchmarks/results/gate_a_oracle.json

echo "=== GATE A COMPLETE ==="
