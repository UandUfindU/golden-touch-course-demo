import os
import sys
import subprocess
import time

# Helper colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

TEST_DIR = os.path.join(os.path.dirname(__file__), "service_test")

TEST_MAP = {
    "1": ("test_chat_basic.py", "Basic Chat Connectivity"),
    "2": ("test_graph_gen.py", "Graph Generation & Edge Verification"),
    "3": ("test_backtest.py", "Backtest Execution Flow")
}

def run_test(filename, description):
    print(f"\n{BOLD}Running: {description}...{RESET}")
    print("-" * 50)
    script_path = os.path.join(TEST_DIR, filename)
    
    start = time.time()
    try:
        # Run subprocess and stream output
        result = subprocess.run([sys.executable, "-u", script_path], check=False)
        duration = time.time() - start
        
        print("-" * 50)
        if result.returncode == 0:
            print(f"{GREEN}PASS{RESET} ({duration:.2f}s)")
            return True
        else:
            print(f"{RED}FAIL{RESET} (Exit Code: {result.returncode})")
            return False
    except Exception as e:
        print(f"{RED}ERROR{RESET}: Failed to execute script: {e}")
        return False

def show_menu():
    while True:
        print(f"\n{BOLD}=== Backend Service Verification Suite ==={RESET}")
        print("0. Run ALL Tests")
        for key, (script, desc) in TEST_MAP.items():
            print(f"{key}. {desc}")
        print("q. Quit")
        
        choice = input("\nSelect Option: ").strip().lower()
        
        if choice == 'q':
            sys.exit(0)
            
        elif choice == '0':
            results = []
            for k in sorted(TEST_MAP.keys()):
                script, desc = TEST_MAP[k]
                success = run_test(script, desc)
                results.append((desc, success))
            
            print(f"\n{BOLD}=== Summary ==={RESET}")
            for desc, success in results:
                status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
                print(f"{status} - {desc}")
                
        elif choice in TEST_MAP:
            script, desc = TEST_MAP[choice]
            run_test(script, desc)
        else:
            print("Invalid selection.")

if __name__ == "__main__":
    if not os.path.exists(TEST_DIR):
        print(f"{RED}Error: Test directory '{TEST_DIR}' not found!{RESET}")
        sys.exit(1)
        
    try:
        show_menu()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
