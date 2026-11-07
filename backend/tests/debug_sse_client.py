import requests
import json
import sys

# Backend URL
API_URL = "http://localhost:8000/api/v1/chat/send"

def debug_sse():
    payload = {
        "session_id": "debug-session-001",
        "message": "构建一个双均线策略，快线5，慢线20",
        "layer": "offline",
        "mode": "auto",
        "model": "glm-4-flash",
        "client_context": {}
    }
    
    print(f"Connecting to {API_URL}...")
    try:
        with requests.post(API_URL, json=payload, stream=True) as r:
            if r.status_code != 200:
                print(f"Error: {r.status_code} - {r.text}")
                return

            print("Connected! Listening for events...\n")
            
            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:]
                        try:
                            event = json.loads(json_str)
                            if event["type"] == "graph_generated":
                                print("\n[GRAPH GENERATED EVENT]")
                                dag = event.get("dag", {})
                                nodes = dag.get("nodes", [])
                                edges = dag.get("edges", [])
                                print(f"Nodes count: {len(nodes)}")
                                print(f"Edges count: {len(edges)}")
                                print("Edges Dump saved to edges_dump.json")
                                with open("edges_dump.json", "w", encoding="utf-8") as f:
                                    json.dump(edges, f, indent=2, ensure_ascii=False)
                                print("-" * 50)
                                return # Found what we needed
                            else:
                                print(f"Event: {event['type']}")
                        except json.JSONDecodeError:
                            print(f"Could not parse JSON: {json_str}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    debug_sse()
