"""
API Test Cases for Runs Router (/api/v1/runs)
Tests workflow run triggering and status retrieval.
Note: These tests require a database with existing workflows.
"""

import requests
import json
import sys
import time
import uuid

RUNS_URL = "http://localhost:8000/api/v1/runs"
WORKFLOWS_URL = "http://localhost:8000/api/v1/workflows"


def create_test_workflow():
    """Helper: Create a workflow for testing runs."""
    workflow_data = {
        "name": f"Run Test Workflow {int(time.time())}",
        "description": "Workflow for run testing",
        "graph_json": {
            "nodes": [
                {"id": "n1", "type": "data.fetch_crypto", "data": {"symbol": "BTC/USDT"}}
            ],
            "edges": []
        }
    }
    
    try:
        response = requests.post(WORKFLOWS_URL + "/", json=workflow_data)
        if response.status_code == 200:
            return response.json().get("id")
        return None
    except Exception:
        return None


def cleanup_workflow(workflow_id: str):
    """Helper: Delete a test workflow."""
    try:
        requests.delete(f"{WORKFLOWS_URL}/{workflow_id}")
    except Exception:
        pass


def test_trigger_run(workflow_id: str):
    """Test triggering a workflow run."""
    print(f"[*] Testing Trigger Run: POST {RUNS_URL}/workflow/{workflow_id}")
    
    try:
        response = requests.post(f"{RUNS_URL}/workflow/{workflow_id}")
        
        if response.status_code == 200:
            run = response.json()
            run_id = run.get("id")
            status = run.get("status")
            print(f"[PASS] Triggered run with ID: {run_id}")
            print(f"  Status: {status}")
            print(f"  Workflow ID: {run.get('workflow_id')}")
            return run_id
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return None


def test_trigger_run_not_found():
    """Test triggering a run for non-existent workflow returns 404."""
    fake_id = str(uuid.uuid4())
    print(f"[*] Testing Trigger Run (Non-Existent Workflow): POST {RUNS_URL}/workflow/{fake_id}")
    
    try:
        response = requests.post(f"{RUNS_URL}/workflow/{fake_id}")
        
        if response.status_code == 404:
            print("[PASS] Correctly returned 404 for non-existent workflow")
            return True
        else:
            print(f"[FAIL] Expected 404, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_get_run_status(run_id: str):
    """Test getting the status of a specific run."""
    print(f"[*] Testing Get Run Status: GET {RUNS_URL}/{run_id}")
    
    try:
        response = requests.get(f"{RUNS_URL}/{run_id}")
        
        if response.status_code == 200:
            run = response.json()
            print(f"[PASS] Retrieved run status")
            print(f"  Run ID: {run.get('id')}")
            print(f"  Status: {run.get('status')}")
            print(f"  Created At: {run.get('created_at', 'N/A')}")
            return True
        else:
            print(f"[FAIL] HTTP Error: {response.status_code}")
            print(response.text)
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_get_run_not_found():
    """Test getting a non-existent run returns 404."""
    fake_id = str(uuid.uuid4())
    print(f"[*] Testing Get Non-Existent Run: GET {RUNS_URL}/{fake_id}")
    
    try:
        response = requests.get(f"{RUNS_URL}/{fake_id}")
        
        if response.status_code == 404:
            print("[PASS] Correctly returned 404 for non-existent run")
            return True
        else:
            print(f"[FAIL] Expected 404, got {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_run_lifecycle():
    """Test full run lifecycle: create workflow -> trigger run -> check status."""
    print("[*] Testing Full Run Lifecycle")
    
    # 1. Create a workflow
    workflow_id = create_test_workflow()
    if not workflow_id:
        print("[SKIP] Could not create test workflow (DB may not be available)")
        return None  # Skip, not fail
    
    print(f"  Created workflow: {workflow_id}")
    
    try:
        # 2. Trigger a run
        response = requests.post(f"{RUNS_URL}/workflow/{workflow_id}")
        
        if response.status_code != 200:
            print(f"[FAIL] Could not trigger run: {response.status_code}")
            cleanup_workflow(workflow_id)
            return False
        
        run = response.json()
        run_id = run.get("id")
        print(f"  Triggered run: {run_id}")
        
        # 3. Check run status
        status_response = requests.get(f"{RUNS_URL}/{run_id}")
        
        if status_response.status_code != 200:
            print(f"[FAIL] Could not get run status: {status_response.status_code}")
            cleanup_workflow(workflow_id)
            return False
        
        print(f"  Run status: {status_response.json().get('status')}")
        
        # Cleanup
        cleanup_workflow(workflow_id)
        
        print("[PASS] Full run lifecycle completed successfully")
        return True
        
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        cleanup_workflow(workflow_id)
        return False


def run_all_tests():
    """Run all runs API tests."""
    print("=" * 60)
    print("RUNS API TEST SUITE")
    print("=" * 60)
    print("[NOTE] These tests require database connectivity")
    print()
    
    results = []
    
    # Test 1: Trigger run for non-existent workflow
    results.append(("Trigger Run (404)", test_trigger_run_not_found()))
    
    # Test 2: Get non-existent run
    results.append(("Get Run Status (404)", test_get_run_not_found()))
    
    # Test 3: Full lifecycle test
    lifecycle_result = test_run_lifecycle()
    if lifecycle_result is not None:
        results.append(("Full Run Lifecycle", lifecycle_result))
    else:
        print("[SKIP] Skipping lifecycle test - DB not available")
    
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
