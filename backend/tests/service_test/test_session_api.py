"""
API Test Cases for Session Router (/api/v1/session, /api/v1/graph)
Tests session management and layer graph operations.
"""

import requests
import json
import sys
import time

SESSION_URL = "http://localhost:8000/api/v1/session"
GRAPH_URL = "http://localhost:8000/api/v1/graph"


def test_get_session_info():
    """Test getting session information."""
    session_id = f"test-session-{int(time.time())}"
    print(f"[*] Testing Get Session Info: GET {SESSION_URL}/{session_id}")
    
    try:
        response = requests.get(f"{SESSION_URL}/{session_id}")
        
        if response.status_code == 200:
            session = response.json()
            print(f"[PASS] Retrieved session info")
            print(f"  Session ID: {session.get('session_id', session_id)}")
            print(f"  Active Layer: {session.get('active_layer', 'N/A')}")
            return session_id
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return None


def test_switch_layer(session_id: str, layer: str = "online"):
    """Test switching the active layer."""
    print(f"[*] Testing Switch Layer: POST {SESSION_URL}/{session_id}/switch")
    
    try:
        response = requests.post(
            f"{SESSION_URL}/{session_id}/switch",
            json={"layer": layer}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[PASS] Switched to layer: {layer}")
            return True
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_get_layer_graph(session_id: str, layer: str = "offline"):
    """Test getting graph data for a specific layer."""
    print(f"[*] Testing Get Layer Graph: GET {GRAPH_URL}/{session_id}/{layer}")
    
    try:
        response = requests.get(f"{GRAPH_URL}/{session_id}/{layer}")
        
        if response.status_code == 200:
            graph = response.json()
            nodes = graph.get("nodes", [])
            edges = graph.get("edges", [])
            print(f"[PASS] Retrieved graph: {len(nodes)} nodes, {len(edges)} edges")
            return True
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_update_layer_graph(session_id: str, layer: str = "offline"):
    """Test updating graph data for a specific layer (autosave)."""
    print(f"[*] Testing Update Layer Graph: POST {GRAPH_URL}/{session_id}/{layer}")
    
    graph_data = {
        "nodes": [
            {"id": "n1", "type": "data.fetch_crypto", "data": {"symbol": "BTC/USDT"}},
            {"id": "n2", "type": "indicator.ma", "data": {"window": 10}},
            {"id": "n3", "type": "indicator.ma", "data": {"window": 20}}
        ],
        "edges": [
            {"source": "n1", "target": "n2", "type": "data"},
            {"source": "n1", "target": "n3", "type": "data"}
        ]
    }
    
    try:
        response = requests.post(
            f"{GRAPH_URL}/{session_id}/{layer}",
            json=graph_data
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "ok":
                print(f"[PASS] Updated graph for layer: {result.get('updated_layer')}")
                return True
            else:
                print("[FAIL] Response status not 'ok'")
                return False
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_graph_persistence(session_id: str, layer: str = "offline"):
    """Test that graph updates are persisted."""
    print("[*] Testing Graph Persistence")
    
    # Create unique test data
    timestamp = int(time.time())
    graph_data = {
        "nodes": [
            {"id": f"persist-{timestamp}", "type": "test.node", "data": {"value": timestamp}}
        ],
        "edges": []
    }
    
    try:
        # Update graph
        update_response = requests.post(
            f"{GRAPH_URL}/{session_id}/{layer}",
            json=graph_data
        )
        
        if update_response.status_code != 200:
            print(f"[FAIL] Failed to update graph: {update_response.status_code}")
            return False
        
        # Retrieve graph and verify
        get_response = requests.get(f"{GRAPH_URL}/{session_id}/{layer}")
        
        if get_response.status_code != 200:
            print(f"[FAIL] Failed to get graph: {get_response.status_code}")
            return False
        
        retrieved_graph = get_response.json()
        nodes = retrieved_graph.get("nodes", [])
        
        # Check if our node exists
        found = any(n.get("id") == f"persist-{timestamp}" for n in nodes)
        
        if found:
            print("[PASS] Graph data persisted correctly")
            return True
        else:
            print("[FAIL] Could not find persisted node")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_multiple_layers(session_id: str):
    """Test operations across different layers."""
    print("[*] Testing Multiple Layer Operations")
    
    layers = ["online", "offline", "tool"]
    results = []
    
    for layer in layers:
        try:
            # Update each layer with unique data
            graph_data = {
                "nodes": [{"id": f"layer-{layer}", "type": "test.node", "data": {"layer": layer}}],
                "edges": []
            }
            
            response = requests.post(f"{GRAPH_URL}/{session_id}/{layer}", json=graph_data)
            results.append((layer, response.status_code == 200))
            
        except Exception:
            results.append((layer, False))
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print(f"[PASS] Successfully operated on all {len(layers)} layers")
    else:
        failed_layers = [r[0] for r in results if not r[1]]
        print(f"[FAIL] Failed on layers: {failed_layers}")
    
    return all_passed


def run_all_tests():
    """Run all session API tests."""
    print("=" * 60)
    print("SESSION API TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: Get session info (creates new session)
    session_id = test_get_session_info()
    results.append(("Get Session Info", session_id is not None))
    
    if session_id:
        # Test 2: Switch layer
        results.append(("Switch Layer", test_switch_layer(session_id, "online")))
        
        # Test 3: Get layer graph
        results.append(("Get Layer Graph", test_get_layer_graph(session_id, "offline")))
        
        # Test 4: Update layer graph
        results.append(("Update Layer Graph", test_update_layer_graph(session_id, "offline")))
        
        # Test 5: Graph persistence
        results.append(("Graph Persistence", test_graph_persistence(session_id, "offline")))
        
        # Test 6: Multiple layers
        results.append(("Multiple Layer Operations", test_multiple_layers(session_id)))
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
