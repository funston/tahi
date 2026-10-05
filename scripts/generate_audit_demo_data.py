import json

import tiktoken

print("Packaging real graph & corpus data for audit demo...")

# Load real graph and corpus
graph = json.load(open("data/graphrag_bench/graph_clean/graph.json"))
corpus_text = json.load(open("data/graphrag_bench/medical_corpus.json"))["context"]

# Re-chunk text
enc = tiktoken.get_encoding("cl100k_base")
tokens = enc.encode(corpus_text)
chunk_size = 1200
chunks = {}
for i in range(0, len(tokens), chunk_size):
    chunk_tokens = tokens[i:i+chunk_size]
    chunk_id = f"chunk_{i//chunk_size:04d}"
    chunks[chunk_id] = enc.decode(chunk_tokens)

# Prepare real audit data
audit_data = {
    "total_nodes": len(graph["nodes"]),
    "total_edges": len(graph["edges"]),
    "sample_edges": graph["edges"][:500],  # Top 500 real edges for instant browser UI
    "chunks": chunks
}

with open("docs/audit_data.json", "w") as f:
    json.dump(audit_data, f)

print(f"Wrote docs/audit_data.json with {len(audit_data['sample_edges'])} real edges and {len(chunks)} real text chunks.")
