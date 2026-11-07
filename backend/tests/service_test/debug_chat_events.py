"""Debug: 检查Chat API返回的事件类型"""
import requests
import json
import time

url = "http://localhost:8000/api/v1/chat/send"
payload = {
    "session_id": f"debug-{int(time.time())}",
    "message": "帮我创建一个简单的BTC均线交叉策略",
    "layer": "offline",
    "mode": "auto",
    "model": "glm-4-flash"
}

print("Sending request...")
with requests.post(url, json=payload, stream=True, timeout=120) as r:
    print(f"Status: {r.status_code}")
    for line in r.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data: "):
                event = json.loads(decoded[6:])
                etype = event.get("type")
                print(f"\nEvent Type: {etype}")
                
                if etype == "graph_generated":
                    dag = event.get("dag", {})
                    print(f"  DAG nodes: {len(dag.get('nodes', []))}")
                    print(f"  DAG edges: {len(dag.get('edges', []))}")
                elif etype == "message":
                    content = event.get("content", "")[:150]
                    print(f"  Content: {content}...")
                elif etype == "error":
                    print(f"  Error: {event.get('content')}")
                elif etype == "tool_call":
                    print(f"  Tool: {event.get('name')}")
                elif etype == "status":
                    print(f"  Status: {event.get('content')}")
                else:
                    print(f"  Full event: {json.dumps(event, ensure_ascii=False)[:200]}")
