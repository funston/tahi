import argparse
import json

import tiktoken


def main():
    parser = argparse.ArgumentParser(description="TAHI Real 1-Click Audit Verification CLI")
    parser.add_argument("--question-idx", type=int, default=0, help="Question index in medical_questions.json")
    args = parser.parse_args()

    # Load real datasets
    questions = json.load(open("data/graphrag_bench/medical_questions.json"))
    graph = json.load(open("data/graphrag_bench/graph_clean/graph.json"))
    corpus_text = json.load(open("data/graphrag_bench/medical_corpus.json"))["context"]

    # Re-chunk text
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(corpus_text)
    chunks = {}
    for i in range(0, len(tokens), 1200):
        chunk_tokens = tokens[i:i+1200]
        chunks[f"chunk_{i//1200:04d}"] = enc.decode(chunk_tokens)

    q = questions[args.question_idx]

    print("\n============================================================")
    print("TAHI REAL 1-CLICK AUDIT VERIFICATION CLI")
    print("============================================================")
    print(f"Question Index: #{args.question_idx} [{q['question_type']}]")
    print(f"Question     : {q['question']}\n")

    # Match query words to graph edges
    words = [w.lower() for w in q['question'].split() if len(w) > 3]
    matched_edges = [e for e in graph['edges'] if any(w in e['source'].lower() or w in e['target'].lower() or w in e['relation'].lower() for w in words)]

    print(f"TAHI Graph Traversal Matched {len(matched_edges)} Real Edges in graph_clean/graph.json")
    print("------------------------------------------------------------")

    for idx, e in enumerate(matched_edges[:3]):
        cid = e.get("source_chunk_id")
        raw_chunk = chunks.get(cid, "Chunk text not found")
        print(f"\n[{idx+1}] Graph Edge Claim:")
        print(f"    ({e['source']}) --[{e['relation']}]--> ({e['target']})")
        print(f"    Source Chunk Pointer: {cid}")
        print("    1-Click Audited Corpus Sentence:")
        print(f"    \"{raw_chunk[:250].strip()}...\"")

    print("\n============================================================\n")

if __name__ == "__main__":
    main()
