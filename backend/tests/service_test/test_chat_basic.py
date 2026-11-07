import requests
import json
import sys
import time

API_URL = "http://localhost:8000/api/v1/chat/send"

def test_chat_basic():
    print(f"[*] Testing Chat Connectivity to: {API_URL}")
    payload = {
        "session_id": f"test-chat-{int(time.time())}",
        "message": "hello", # Simple message
        "layer": "offline",
        "mode": "fast", # Use fast mode
        "model": "glm-4-flash"
    }

    try:
        with requests.post(API_URL, json=payload, stream=True) as r:
            if r.status_code != 200:
                print(f"[FAIL] HTTP Error: {r.status_code}")
                return False
            
            print("[*] Connected. Listening for response...")
            has_response = False
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        data = json.loads(decoded[6:])
                        if data["type"] == "message":
                            print(f"[PASS] Received Message: {data['content'][:50]}...")
                            has_response = True
                            return True
            
            if not has_response:
                print("[FAIL] Connection closed without message.")
                return False

    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False

if __name__ == "__main__":
    success = test_chat_basic()
    sys.exit(0 if success else 1)
