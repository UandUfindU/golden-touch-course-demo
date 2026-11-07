"""
API Test Cases for Workflow Router (/api/v1/workflows)
Tests CRUD operations for Workflow management.
"""

import requests
import json
import sys
import time
import uuid

BASE_URL = "http://localhost:8000/api/v1/workflows"


def test_create_workflow():
    """Test creating a new workflow."""
    print(f"[*] Testing Workflow Creation: POST {BASE_URL}/")
    
    workflow_data = {
        "name": f"Test Workflow {int(time.time())}",
        "description": "A test workflow created by API test",
        "graph_json": {
            "nodes": [
                {"id": "n1", "type": "data.fetch_crypto", "data": {"symbol": "BTC/USDT"}},
                {"id": "n2", "type": "indicator.ma", "data": {"window": 20}}
            ],
            "edges": [
                {"source": "n1", "target": "n2", "type": "data"}
            ]
        }
    }
    
    try:
        response = requests.post(BASE_URL + "/", json=workflow_data)
        
        if response.status_code == 200:
            result = response.json()
            workflow_id = result.get("id")
            print(f"[PASS] Created workflow with ID: {workflow_id}")
            return workflow_id
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return None


def test_list_workflows():
    """Test listing all workflows."""
    print(f"[*] Testing Workflow List: GET {BASE_URL}/")
    
    try:
        response = requests.get(BASE_URL + "/")
        
        if response.status_code == 200:
            workflows = response.json()
            print(f"[PASS] Retrieved {len(workflows)} workflows")
            return True
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_get_workflow(workflow_id: str):
    """Test getting a specific workflow by ID."""
    print(f"[*] Testing Get Workflow: GET {BASE_URL}/{workflow_id}")
    
    try:
        response = requests.get(f"{BASE_URL}/{workflow_id}")
        
        if response.status_code == 200:
            workflow = response.json()
            print(f"[PASS] Retrieved workflow: {workflow.get('name')}")
            return True
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_get_workflow_not_found():
    """Test getting a non-existent workflow returns 404."""
    fake_id = str(uuid.uuid4())
    print(f"[*] Testing Get Non-Existent Workflow: GET {BASE_URL}/{fake_id}")
    
    try:
        response = requests.get(f"{BASE_URL}/{fake_id}")
        
        if response.status_code == 404:
            print("[PASS] Correctly returned 404 for non-existent workflow")
            return True
        else:
            print(f"[FAIL] Expected 404, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_update_workflow(workflow_id: str):
    """Test updating a workflow."""
    print(f"[*] Testing Update Workflow: PUT {BASE_URL}/{workflow_id}")
    
    update_data = {
        "name": f"Updated Workflow {int(time.time())}",
        "description": "Updated description",
        "graph_json": {
            "nodes": [
                {"id": "n1", "type": "data.fetch_crypto", "data": {"symbol": "ETH/USDT"}}
            ],
            "edges": []
        }
    }
    
    try:
        response = requests.put(f"{BASE_URL}/{workflow_id}", json=update_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"[PASS] Updated workflow: {result.get('name')}")
            return True
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_delete_workflow(workflow_id: str):
    """Test deleting a workflow."""
    print(f"[*] Testing Delete Workflow: DELETE {BASE_URL}/{workflow_id}")
    
    try:
        response = requests.delete(f"{BASE_URL}/{workflow_id}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print("[PASS] Successfully deleted workflow")
                return True
            else:
                print("[FAIL] Delete did not return ok=True")
                return False
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_delete_workflow_not_found():
    """Test deleting a non-existent workflow returns 404."""
    fake_id = str(uuid.uuid4())
    print(f"[*] Testing Delete Non-Existent Workflow: DELETE {BASE_URL}/{fake_id}")
    
    try:
        response = requests.delete(f"{BASE_URL}/{fake_id}")
        
        if response.status_code == 404:
            print("[PASS] Correctly returned 404 for non-existent workflow")
            return True
        else:
            print(f"[FAIL] Expected 404, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def run_all_tests():
    """Run all workflow API tests."""
    print("=" * 60)
    print("WORKFLOW API TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: Create a workflow
    workflow_id = test_create_workflow()
    results.append(("Create Workflow", workflow_id is not None))
    
    if workflow_id:
        # Test 2: List workflows
        results.append(("List Workflows", test_list_workflows()))
        
        # Test 3: Get specific workflow
        results.append(("Get Workflow", test_get_workflow(workflow_id)))
        
        # Test 4: Get non-existent workflow
        results.append(("Get Non-Existent Workflow (404)", test_get_workflow_not_found()))
        
        # Test 5: Update workflow
        results.append(("Update Workflow", test_update_workflow(workflow_id)))
        
        # Test 6: Delete workflow
        results.append(("Delete Workflow", test_delete_workflow(workflow_id)))
        
        # Test 7: Delete non-existent workflow
        results.append(("Delete Non-Existent Workflow (404)", test_delete_workflow_not_found()))
    
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
