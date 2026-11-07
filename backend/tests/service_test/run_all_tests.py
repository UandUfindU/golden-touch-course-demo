"""
Test Runner for Golden Touch Backend API Tests

Usage:
    python run_all_tests.py           # Run all tests
    python run_all_tests.py chat      # Run specific test module
    python run_all_tests.py --list    # List available tests
"""

import subprocess
import sys
import os
from pathlib import Path

# Test modules
TEST_MODULES = {
    "chat": "test_chat_api.py",
    "chat_basic": "test_chat_basic.py",
    "nodes": "test_nodes_api.py",
    "session": "test_session_api.py",
    "workflow": "test_workflow_api.py",
    "runs": "test_runs_api.py",
    "execution": "test_execution_api.py",
    "backtest": "test_backtest.py",
}

def get_test_dir():
    return Path(__file__).parent

def run_test(name: str, file: str) -> bool:
    """Run a single test file."""
    print(f"\n{'='*60}")
    print(f"RUNNING: {name}")
    print(f"{'='*60}")
    
    test_path = get_test_dir() / file
    
    if not test_path.exists():
        print(f"[SKIP] Test file not found: {file}")
        return True
    
    result = subprocess.run(
        [sys.executable, str(test_path)],
        cwd=str(get_test_dir())
    )
    
    return result.returncode == 0

def run_all_tests():
    """Run all test modules."""
    results = {}
    
    for name, file in TEST_MODULES.items():
        results[name] = run_test(name, file)
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    passed = sum(1 for r in results.values() if r)
    failed = sum(1 for r in results.values() if not r)
    
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    return failed == 0

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == "--list":
            print("Available test modules:")
            for name, file in TEST_MODULES.items():
                print(f"  {name}: {file}")
            return
        
        if arg in TEST_MODULES:
            success = run_test(arg, TEST_MODULES[arg])
            sys.exit(0 if success else 1)
        
        print(f"Unknown test: {arg}")
        print("Use --list to see available tests")
        sys.exit(1)
    
    success = run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
