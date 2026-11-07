"""
API Test Cases for Nodes Router (/api/v1/nodes)
Tests node listing and node detail retrieval.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/v1/nodes"


def test_list_nodes():
    """Test listing all available nodes."""
    print(f"[*] Testing Node List: GET {BASE_URL}/")
    
    try:
        response = requests.get(BASE_URL + "/")
        
        if response.status_code == 200:
            nodes = response.json()
            print(f"[PASS] Retrieved {len(nodes)} nodes")
            
            # Print some node information
            if nodes:
                print("  Available node types:")
                for node in nodes[:5]:  # Show first 5
                    print(f"    - {node.get('name', 'unknown')}: {node.get('description', 'N/A')[:50]}")
                if len(nodes) > 5:
                    print(f"    ... and {len(nodes) - 5} more")
            
            return nodes
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return None


def test_get_node_details(node_name: str):
    """Test getting details for a specific node type."""
    print(f"[*] Testing Get Node Details: GET {BASE_URL}/{node_name}")
    
    try:
        response = requests.get(f"{BASE_URL}/{node_name}")
        
        if response.status_code == 200:
            details = response.json()
            print(f"[PASS] Retrieved node details for: {node_name}")
            print(f"  Name: {details.get('name')}")
            print(f"  Category: {details.get('category', 'N/A')}")
            print(f"  Description: {details.get('description', 'N/A')[:60]}...")
            return True
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_get_node_not_found():
    """Test getting a non-existent node returns 404."""
    fake_node = "non_existent_node_type_12345"
    print(f"[*] Testing Get Non-Existent Node: GET {BASE_URL}/{fake_node}")
    
    try:
        response = requests.get(f"{BASE_URL}/{fake_node}")
        
        if response.status_code == 404:
            print("[PASS] Correctly returned 404 for non-existent node")
            return True
        else:
            print(f"[FAIL] Expected 404, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_node_metadata_structure():
    """Test that node metadata has required fields."""
    print("[*] Testing Node Metadata Structure")
    
    try:
        response = requests.get(BASE_URL + "/")
        
        if response.status_code != 200:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            return False
        
        nodes = response.json()
        
        if not nodes:
            print("[WARN] No nodes available to test")
            return True
        
        required_fields = ["name", "category"]
        
        for node in nodes:
            for field in required_fields:
                if field not in node:
                    print(f"[FAIL] Node missing required field '{field}': {node}")
                    return False
        
        print(f"[PASS] All {len(nodes)} nodes have required metadata fields")
        return True
        
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_node_categories():
    """Test that nodes are properly categorized."""
    print("[*] Testing Node Categories")
    
    try:
        response = requests.get(BASE_URL + "/")
        
        if response.status_code != 200:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            return False
        
        nodes = response.json()
        
        categories = {}
        for node in nodes:
            category = node.get("category", "unknown")
            if category not in categories:
                categories[category] = []
            categories[category].append(node.get("name"))
        
        print(f"[PASS] Found {len(categories)} node categories:")
        for cat, node_list in categories.items():
            print(f"    {cat}: {len(node_list)} nodes")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def run_all_tests():
    """Run all node API tests."""
    print("=" * 60)
    print("NODES API TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: List all nodes
    nodes = test_list_nodes()
    results.append(("List Nodes", nodes is not None))
    
    # Test 2: Get specific node details (if nodes exist)
    if nodes and len(nodes) > 0:
        first_node = nodes[0].get("name")
        if first_node:
            results.append(("Get Node Details", test_get_node_details(first_node)))
    
    # Test 3: Get non-existent node
    results.append(("Get Non-Existent Node (404)", test_get_node_not_found()))
    
    # Test 4: Validate metadata structure
    results.append(("Node Metadata Structure", test_node_metadata_structure()))
    
    # Test 5: Test node categories
    results.append(("Node Categories", test_node_categories()))
    
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
