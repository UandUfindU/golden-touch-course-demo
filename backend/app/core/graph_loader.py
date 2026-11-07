import os
import yaml
from typing import Dict, Any

class GraphLoader:
    """Helper to load standard graphs from file system."""
    
    BASE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "graphs", "standard")
    
    @classmethod
    def load_graph(cls, graph_name: str) -> Dict[str, Any]:
        """
        Load a graph definition from YAML and resolve file:// references.
        
        Args:
            graph_name: e.g. "build_strategy" or "build_workflow"
            
        Returns:
            Dict containing the graph definition (nodes, edges)
        """
        # Security check: basic path traversal prevention
        if ".." in graph_name or "/" in graph_name or "\\" in graph_name:
             raise ValueError("Invalid graph name")
             
        graph_dir = os.path.join(cls.BASE_PATH, graph_name)
        file_path = os.path.join(graph_dir, "graph.yaml")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Standard graph not found: {graph_name} at {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        # Resolve file:// references
        return cls._resolve_file_refs(data, graph_dir)
        
    @classmethod
    def _resolve_file_refs(cls, data: Any, base_dir: str) -> Any:
        """Recursively resolve file:// references in graph data."""
        if isinstance(data, dict):
            return {k: cls._resolve_file_refs(v, base_dir) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls._resolve_file_refs(item, base_dir) for item in data]
        elif isinstance(data, str) and data.startswith("file://"):
            rel_path = data[7:] # strip prefix
            # Resolve relative to graph directory
            full_path = os.path.join(base_dir, rel_path)
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"[WARN] Failed to load referenced file {full_path}: {e}")
                return data # fallback to original string
        else:
            return data

    @classmethod 
    def get_available_graphs(cls):
        """List available standard graphs."""
        if not os.path.exists(cls.BASE_PATH):
            return []
        return [d for d in os.listdir(cls.BASE_PATH) if os.path.isdir(os.path.join(cls.BASE_PATH, d))]
