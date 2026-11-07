import requests
import json
import sys
import time

# Configuration
API_URL = "http://localhost:8000/api/v1/chat/send"

def test_graph_generation():
    print(f"[*] Testing Graph Generation from: {API_URL}")
    
    payload = {
        "session_id": f"test-graph-{int(time.time())}",
        "message": "构建一个双均线策略，快线5，慢线20",
        "layer": "offline",
        "mode": "auto",
        "model": "glm-4-flash",
        "client_context": {}
    }
    
    start_time = time.time()
    try:
        with requests.post(API_URL, json=payload, stream=True) as r:
            if r.status_code != 200:
                print(f"[FAIL] HTTP Error: {r.status_code} - {r.text}")
                return False

            print("[*] Connected. Waiting for graph_generated event...")
            
            graph_received = False
            edges_valid = True # Assistive flag
            
            for line in r.iter_lines():
                if time.time() - start_time > 60:
                    print("[FAIL] Timeout waiting for graph generation (60s)")
                    return False
                    
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        json_str = decoded_line[6:]
                        try:
                            event = json.loads(json_str)
                            
                            if event["type"] == "status":
                                print(f"  -> Status: {event.get('content')}")
                                
                            elif event["type"] == "graph_generated":
                                print("\n[SUCCESS] Graph Generated Event Received!")
                                dag = event.get("dag", {})
                                nodes = dag.get("nodes", [])
                                edges = dag.get("edges", [])
                                
                                print(f"  Nodes: {len(nodes)}")
                                print(f"  Edges: {len(edges)}")
                                
                                # Validate Edges
                                if not edges:
                                    print("[WARN] No edges generated (simple graph?).")
                                else:
                                    print("[*] Validating Edge Ports...")
                                    for idx, edge in enumerate(edges):
                                        src_port = edge.get("source_port")
                                        tgt_port = edge.get("target_port")
                                        
                                        if not src_port or not tgt_port:
                                            print(f"  [FAIL] Edge {idx} missing ports! Source: {edge.get('source')}, Target: {edge.get('target')}")
                                            print(f"         Raw Edge: {edge}")
                                            edges_valid = False
                                        else:
                                            print(f"  [PASS] Edge {idx}: {src_port} -> {tgt_port}")
                                
                                if edges_valid:
                                    print("[SUCCESS] All edges have valid ports.")
                                    return True
                                else:
                                    print("[FAIL] Some edges are missing port information.")
                                    return False
                                    
                        except json.JSONDecodeError:
                            pass
                            
    except Exception as e:
        print(f"[FAIL] Connection error: {e}")
        return False

if __name__ == "__main__":
    success = test_graph_generation()
    sys.exit(0 if success else 1)
