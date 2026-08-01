"""
Train a SchemaSQLCoprocessor-7B specialist model.

Fine-tunes Qwen2.5-Coder-7B-Instruct on grounded schema + question → SQL pairs.
Uses LoRA to fit in ~80GB GPU RAM. For 128GB+ GPUs, increase batch size.

Usage:
    python scripts/train_schema_sql_coprocessor.py \
        --data_path data/schema_sql_train.jsonl \
        --output_dir models/schema_sql_coprocessor_7b \
        --num_epochs 3 \
        --batch_size 4 \
        --gradient_accumulation_steps 4 \
        --lora_r 64 \
        --lora_alpha 128 \
        --learning_rate 2e-4 \
        --max_seq_length 2048
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from datasets import Dataset
from peft import LoraConfig, TaskType
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import SFTTrainer


def format_example(example: dict) -> str:
    """Format one training example as an instruction-following prompt."""
    instruction = example.get("instruction", "")
    input_text = example.get("input", "")
    output = example.get("output", "")

    if input_text:
        prompt = f"{instruction}\n\n### Input:\n{input_text}\n\n### Response:\n{output}"
    else:
        prompt = f"{instruction}\n\n### Response:\n{output}"
    return prompt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_path", required=True, help="JSONL file with instruction/input/output")
    parser.add_argument("--output_dir", required=True, help="Directory to save model")
    parser.add_argument("--base_model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--num_epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=4)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--max_seq_length", type=int, default=2048)
    parser.add_argument("--lora_r", type=int, default=64)
    parser.add_argument("--lora_alpha", type=int, default=128)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument("--warmup_ratio", type=float, default=0.03)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--bf16", action="store_true", default=True)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--use_wandb", action="store_true", default=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    print(f"Loading data from {args.data_path}")
    raw_data = []
    with open(args.data_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            import json
            raw_data.append(json.loads(line))

    dataset = Dataset.from_list(raw_data)
    print(f"Loaded {len(dataset)} examples")

    # Load tokenizer and model
    print(f"Loading base model {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )

    # LoRA config
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )

    # Training args
    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=args.num_epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=args.warmup_ratio,
        weight_decay=args.weight_decay,
        bf16=args.bf16 and not args.fp16,
        fp16=args.fp16,
        logging_steps=10,
        save_steps=500,
        save_total_limit=3,
        report_to="wandb" if args.use_wandb else "none",
        run_name="octo-schema-sql-coprocessor-7b",
        seed=args.seed,
    )

    # Trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
        peft_config=lora_config,
        formatting_func=format_example,
        max_seq_length=args.max_seq_length,
    )

    # Train
    print("Starting training...")
    trainer.train()

    # Save adapter
    adapter_dir = output_dir / "adapter"
    trainer.save_model(str(adapter_dir))
    print(f"Saved adapter to {adapter_dir}")

    # Merge and save final model
    print("Merging LoRA weights and saving final model...")
    from peft import PeftModel

    merged = PeftModel.from_pretrained(model, str(adapter_dir))
    merged = merged.merge_and_unload()
    merged_dir = output_dir / "final_merged"
    merged.save_pretrained(str(merged_dir))
    tokenizer.save_pretrained(str(merged_dir))
    print(f"Saved merged model to {merged_dir}")


if __name__ == "__main__":
    main()
