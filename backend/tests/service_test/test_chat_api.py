"""
API Test Cases for Chat Router (/api/v1/chat)
Tests chat messaging and history retrieval.
"""

import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000/api/v1/chat"


def test_chat_send_basic():
    """Test basic chat message sending."""
    print(f"[*] Testing Chat Send: POST {BASE_URL}/send")
    
    session_id = f"test-chat-{int(time.time())}"
    payload = {
        "session_id": session_id,
        "message": "Hello, this is a test",
        "layer": "offline",
        "mode": "fast",
        "model": "glm-4-flash"
    }
    
    try:
        with requests.post(f"{BASE_URL}/send", json=payload, stream=True, timeout=60) as r:
            if r.status_code != 200:
                print(f"[FAIL] HTTP Error: {r.status_code}")
                return None
            
            print("[*] Connected. Streaming...")
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        event = json.loads(decoded[6:])
                        if event.get("type") == "message":
                            print(f"[PASS] Got message: {event.get('content', '')[:50]}...")
                            return session_id
            return session_id
            
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return None


def test_chat_with_context():
    """Test chat with client context."""
    print(f"[*] Testing Chat with Context")
    
    payload = {
        "session_id": f"test-ctx-{int(time.time())}",
        "message": "Create a MA strategy",
        "layer": "offline",
        "mode": "auto",
        "model": "glm-4-flash",
        "client_context": {"current_nodes": [], "current_edges": []}
    }
    
    try:
        with requests.post(f"{BASE_URL}/send", json=payload, stream=True, timeout=60) as r:
            if r.status_code == 200:
                print("[PASS] Chat with context accepted")
                return True
            print(f"[FAIL] HTTP Error: {r.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def test_chat_get_history(session_id: str):
    """Test getting chat history."""
    print(f"[*] Testing Get History: GET {BASE_URL}/history/{session_id}")
    
    try:
        response = requests.get(f"{BASE_URL}/history/{session_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"[PASS] Retrieved {len(data.get('messages', []))} messages")
            return True
        print(f"[FAIL] HTTP Error: {response.status_code}")
        return False
    except Exception as e:
        print(f"[FAIL] Exception: {e}")
        return False


def run_all_tests():
    """Run all chat API tests."""
    print("=" * 60)
    print("CHAT API TEST SUITE")
    print("=" * 60)
    
    results = []
    
    session_id = test_chat_send_basic()
    results.append(("Chat Send Basic", session_id is not None))
    results.append(("Chat with Context", test_chat_with_context()))
    
    if session_id:
        results.append(("Get Chat History", test_chat_get_history(session_id)))
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    for name, result in results:
        print(f"  [{'PASS' if result else 'FAIL'}] {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
