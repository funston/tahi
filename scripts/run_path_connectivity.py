import argparse
import json

import networkx as nx


def main():
    parser = argparse.ArgumentParser(description="TAHI Path Connectivity Diagnostic (Shortest Path Distribution L >= 2)")
    parser.add_argument("--graph", type=str, default="data/graphrag_bench/graph_clean/graph.json")
    parser.add_argument("--questions", type=str, default="data/graphrag_bench/medical_questions.json")
    args = parser.parse_args()

    graph_data = json.load(open(args.graph))
    questions = json.load(open(args.questions))

    # Build NetworkX Graph
    G = nx.Graph()
    name_to_node = {}
    for n in graph_data["nodes"]:
        G.add_node(n["id"], name=n.get("name", ""))
        name_to_node[n.get("name", "").lower().strip()] = n["id"]

    for e in graph_data["edges"]:
        G.add_edge(e["source"], e["target"])

    complex_q = [q for q in questions if q.get("question_type") == "Complex Reasoning"]

    print("\n============================================================")
    print("TAHI PATH CONNECTIVITY DIAGNOSTIC (CLAUDE_CHALLENGES §5)")
    print("============================================================")
    print(f"Graph Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}")
    print(f"Complex Reasoning Questions Evaluated: {len(complex_q)}")

    path_lengths = {1: 0, 2: 0, 3: 0, ">=4": 0, "unconnected": 0}
    total_pairs = 0

    for q in complex_q:
        # Match entities from evidence_relations to graph nodes
        ev_text = (q.get("evidence", "") + " " + q.get("evidence_relations", "")).lower()
        matched_node_ids = []
        for name, n_id in name_to_node.items():
            if len(name) > 3 and name in ev_text:
                matched_node_ids.append(n_id)

        # Remove duplicate nodes
        matched_node_ids = list(set(matched_node_ids))

        if len(matched_node_ids) >= 2:
            for i in range(len(matched_node_ids)):
                for j in range(i + 1, len(matched_node_ids)):
                    u, v = matched_node_ids[i], matched_node_ids[j]
                    total_pairs += 1
                    if nx.has_path(G, u, v):
                        length = nx.shortest_path_length(G, u, v)
                        if length == 1:
                            path_lengths[1] += 1
                        elif length == 2:
                            path_lengths[2] += 1
                        elif length == 3:
                            path_lengths[3] += 1
                        else:
                            path_lengths[">=4"] += 1
                    else:
                        path_lengths["unconnected"] += 1

    print(f"Total Gold Entity Pairs Evaluated: {total_pairs}")
    print("Shortest Path Length Distribution:")
    print(f"  - L = 1 (Direct Single Edge) : {path_lengths[1]} ({path_lengths[1]/total_pairs*100:.2f}%)")
    print(f"  - L = 2 (2-Hop Relational)  : {path_lengths[2]} ({path_lengths[2]/total_pairs*100:.2f}%)")
    print(f"  - L = 3 (3-Hop Relational)  : {path_lengths[3]} ({path_lengths[3]/total_pairs*100:.2f}%)")
    print(f"  - L >= 4 (Long Path)        : {path_lengths['>=4']} ({path_lengths['>=4']/total_pairs*100:.2f}%)")
    print(f"  - Unconnected (Infinite)    : {path_lengths['unconnected']} ({path_lengths['unconnected']/total_pairs*100:.2f}%)")

    l2_plus = path_lengths[2] + path_lengths[3] + path_lengths[">=4"]
    print(f"\nMulti-Hop Connected Pairs (L >= 2): {l2_plus} ({l2_plus/total_pairs*100:.2f}%)")
    print("============================================================\n")

if __name__ == "__main__":
    main()
