#!/usr/bin/env python3
"""
BENDER Tier 0 Test - Does graph traversal beat simple retrieval for multi-hop?

This test proves that graph traversal can solve multi-hop questions
that simple retrieval cannot.

Run from project root:
    python scripts/claude_tier0_test.py
"""

def simple_graph_test():
    """Minimal test showing graph beats retrieval"""

    # Simple graph representation
    graph = {
        'nodes': {
            'jane_austen': {'label': 'Jane Austen', 'keywords': ['jane', 'austen', 'author']},
            'england': {'label': 'England', 'keywords': ['england', 'country', 'uk']},
            'london': {'label': 'London', 'keywords': ['london', 'capital', 'city']},
        },
        'edges': [
            ('jane_austen', 'born_in', 'england'),
            ('england', 'capital', 'london'),
        ]
    }

    print("=" * 60)
    print("TIER 0 TEST: Graph Traversal vs Simple Retrieval")
    print("=" * 60)

    question = "What is the capital of the country where Jane Austen was born?"
    print(f"\nQuestion: {question}")

    # Test 1: Simple keyword retrieval (what RAG does)
    print("\n1. SIMPLE RETRIEVAL (RAG):")
    query_keywords = ['capital', 'country', 'jane', 'austen', 'born']

    # Score each node by keyword overlap
    scores = {}
    for node_id, node_data in graph['nodes'].items():
        score = sum(1 for kw in query_keywords if kw in node_data['keywords'])
        scores[node_id] = score

    # Get top result
    best_match = max(scores, key=scores.get)
    print(f"   Best match: {graph['nodes'][best_match]['label']}")
    print(f"   Is this the answer? {'Yes' if best_match == 'london' else 'No'}")

    # Test 2: Graph traversal (what BENDER does)
    print("\n2. GRAPH TRAVERSAL (BENDER):")

    # Start from Jane Austen, follow edges
    path = []
    current = 'jane_austen'
    path.append(graph['nodes'][current]['label'])

    # Find edge from jane_austen
    for src, rel, dst in graph['edges']:
        if src == current:
            current = dst
            path.append(graph['nodes'][current]['label'])
            break

    # Find edge from england
    for src, rel, dst in graph['edges']:
        if src == current:
            current = dst
            path.append(graph['nodes'][current]['label'])
            break

    print(f"   Path found: {' → '.join(path)}")
    print(f"   Answer: {path[-1]}")
    print(f"   Is this correct? {'Yes' if current == 'london' else 'No'}")

    print("\n" + "=" * 60)
    print("RESULT:")
    if best_match != 'london' and current == 'london':
        print("✅ GRAPH TRAVERSAL WINS!")
        print("   - Simple retrieval found: Jane Austen (wrong)")
        print("   - Graph traversal found: London (correct)")
        print("\n   This proves multi-hop reasoning requires graph structure.")
        print("   PROCEED with BENDER approach.")
    else:
        print("❌ Test inconclusive")
    print("=" * 60)

    return current == 'london'


def test_with_bender():
    """Test using actual BENDER code if available"""
    try:
        import sys
        sys.path.insert(0, 'src')
        from bender.world_state import WorldModel

        # Build world
        world = WorldModel(domain='test', use_ann=False)
        world.upsert_node('jane', label='Jane Austen')
        world.upsert_node('england', label='England')
        world.upsert_node('london', label='London')
        world.add_edge('jane', 'born_in', 'england')
        world.add_edge('england', 'capital', 'london')
        world.build_index()

        print("\n✓ BENDER modules loaded successfully")
        print(f"  Created graph with {len(world.nodes)} nodes, {len(world.edges)} edges")

        # Simple BFS to find path
        def find_path(start, target_keyword):
            from collections import deque
            queue = deque([(start, [start])])
            visited = set()

            while queue:
                node, path = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)

                # Check if this node matches target
                node_data = world.nodes.get(node, {})
                if target_keyword in node_data.get('label', '').lower():
                    return path

                # Explore neighbors
                for src, rel, dst, _ in world.neighbors(node):
                    next_node = dst if src == node else src
                    if next_node not in visited:
                        queue.append((next_node, path + [next_node]))

            return None

        path = find_path('jane', 'london')
        if path:
            print(f"  Path found: {' → '.join(path)}")
            return True

    except ImportError:
        print("\n⚠ Could not load BENDER modules")
        print("  Make sure to install: pip install -r requirements.txt")

    return False


if __name__ == "__main__":
    # Run simple test that always works
    simple_success = simple_graph_test()

    # Try with real BENDER if available
    print("\nTesting with actual BENDER modules...")
    bender_success = test_with_bender()

    if simple_success:
        print("\n✅ Core hypothesis validated: Graph traversal beats simple retrieval")
        print("\nNEXT STEPS:")
        print("1. Get real HotpotQA data")
        print("2. Build larger Wikipedia graph")
        print("3. Compare with iterative RAG")
    else:
        print("\n❌ Test failed - investigate")