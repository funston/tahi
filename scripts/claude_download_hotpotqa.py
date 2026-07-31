#!/usr/bin/env python3
"""
Download HotpotQA dataset for benchmarking.

Run from project root:
    python scripts/claude_download_hotpotqa.py
"""

import json
import urllib.request
from pathlib import Path


def download_hotpotqa():
    """Download HotpotQA dev set."""

    # Create datasets directory
    datasets_dir = Path("datasets/hotpotqa")
    datasets_dir.mkdir(parents=True, exist_ok=True)

    # HotpotQA dev set URL (smaller, good for testing)
    dev_url = "http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json"
    dev_file = datasets_dir / "hotpot_dev_distractor_v1.json"

    if dev_file.exists():
        print(f"✓ HotpotQA dev set already exists at {dev_file}")
        return dev_file

    print(f"Downloading HotpotQA dev set...")
    print(f"  URL: {dev_url}")
    print(f"  Destination: {dev_file}")

    try:
        with urllib.request.urlopen(dev_url) as response:
            data = response.read()

        # Save the data
        dev_file.write_bytes(data)

        # Verify it's valid JSON
        parsed = json.loads(data)
        num_examples = len(parsed) if isinstance(parsed, list) else len(parsed.get('data', []))

        print(f"✅ Downloaded {len(data)/1024/1024:.1f} MB")
        print(f"✅ Contains {num_examples} examples")

        # Show sample question
        if isinstance(parsed, dict) and 'data' in parsed:
            sample = parsed['data'][0]
        else:
            sample = parsed[0]

        print(f"\nSample question:")
        print(f"  Q: {sample['question']}")
        print(f"  A: {sample['answer']}")
        print(f"  Type: {sample.get('type', 'unknown')}")

        return dev_file

    except Exception as e:
        print(f"❌ Failed to download: {e}")
        print(f"\nTrying alternative: Creating small sample dataset...")

        # Create a small sample dataset
        sample_data = [
            {
                "_id": "sample_1",
                "question": "What is the capital of the country where the author of Pride and Prejudice was born?",
                "answer": "London",
                "type": "bridge",
                "supporting_facts": [["Jane Austen", 0], ["England", 0]],
            },
            {
                "_id": "sample_2",
                "question": "In what year was the capital of France established as the country's capital?",
                "answer": "508",
                "type": "bridge",
                "supporting_facts": [["Paris", 0], ["France", 0]],
            },
            {
                "_id": "sample_3",
                "question": "Who was the first president of the country that has Washington D.C. as its capital?",
                "answer": "George Washington",
                "type": "bridge",
                "supporting_facts": [["United States", 0], ["Washington D.C.", 0]],
            }
        ]

        sample_file = datasets_dir / "hotpotqa_sample.json"
        sample_file.write_text(json.dumps(sample_data, indent=2))
        print(f"✅ Created sample dataset at {sample_file}")
        return sample_file


def analyze_hotpotqa(file_path):
    """Analyze HotpotQA dataset structure."""

    print(f"\nAnalyzing {file_path.name}...")

    data = json.loads(file_path.read_text())

    # Handle different formats
    if isinstance(data, dict) and 'data' in data:
        examples = data['data']
    else:
        examples = data

    print(f"Total examples: {len(examples)}")

    # Count types
    types = {}
    for ex in examples[:100]:  # Sample first 100
        q_type = ex.get('type', 'unknown')
        types[q_type] = types.get(q_type, 0) + 1

    print(f"Question types (first 100):")
    for t, count in types.items():
        print(f"  {t}: {count}")

    # Find multi-hop examples
    print(f"\nMulti-hop examples (with 2+ supporting facts):")
    multi_hop = []
    for ex in examples[:20]:
        facts = ex.get('supporting_facts', [])
        if len(facts) >= 2:
            multi_hop.append(ex)
            if len(multi_hop) <= 3:
                print(f"  Q: {ex['question']}")
                print(f"  A: {ex['answer']}")
                print(f"  Facts: {[f[0] for f in facts]}")
                print()

    print(f"Found {len(multi_hop)} multi-hop examples in first 20")
    return examples


if __name__ == "__main__":
    file_path = download_hotpotqa()

    if file_path and file_path.exists():
        analyze_hotpotqa(file_path)