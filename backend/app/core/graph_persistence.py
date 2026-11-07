import os
import yaml
import json
from typing import Dict, Any, Optional

class GraphBundle:
    """
    Utilities for managing Graph Bundles (Directory based persistence).
    Structure:
    /graph_name
      ├── graph.yaml       # Nodes, Edges, Metadata
      ├── README.md        # Description
      └── assets/          # Large text files (prompts)
    """
    
    @staticmethod
    def load(bundle_path: str) -> Dict[str, Any]:
        """
        Load a graph bundle into a Graph Definition Dictionary.
        Resolves asset references.
        """
        if not os.path.exists(bundle_path):
            raise FileNotFoundError(f"Graph bundle not found: {bundle_path}")
            
        # 1. Load Graph YAML
        yaml_path = os.path.join(bundle_path, "graph.yaml")
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"Missing graph.yaml in {bundle_path}")
            
        with open(yaml_path, 'r', encoding='utf-8') as f:
            graph_def = yaml.safe_load(f)
            
        # 2. Load README if exists and not already set
        readme_path = os.path.join(bundle_path, "README.md")
        if os.path.exists(readme_path):
            with open(readme_path, 'r', encoding='utf-8') as f:
                description = f.read()
                # Update metadata description if present, or top level?
                # Usually graph_def has 'metadata' field.
                if "metadata" not in graph_def:
                    graph_def["metadata"] = {}
                graph_def["metadata"]["description"] = description

        # 3. Resolve Assets (Deep Traversal)
        # Convention: If a value string starts with "file://", load it from assets/
        GraphBundle._resolve_assets(graph_def, bundle_path)
        
        return graph_def

    @staticmethod
    def save(graph_def: Dict[str, Any], bundle_path: str, overwrite: bool = False):
        """
        Save a Graph Definition dictionary as a Bundle.
        Extracts long strings to assets/ if configured (Future).
        """
        if os.path.exists(bundle_path) and not overwrite:
            raise FileExistsError(f"Bundle path exists: {bundle_path}")
            
        os.makedirs(bundle_path, exist_ok=True)
        assets_dir = os.path.join(bundle_path, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        
        # 1. Extract Description to README
        metadata = graph_def.get("metadata", {})
        description = metadata.get("description", "")
        if description:
            with open(os.path.join(bundle_path, "README.md"), 'w', encoding='utf-8') as f:
                f.write(description)
            # Remove from YAML to avoid duplication? Optional.
            # metadata["description"] = "See README.md"
            
        # 2. Walk and extract Prompts (Optional heuristics)
        # For now, we assume graph_def is fully self-contained or explicitly uses file:// refs.
        # If user wants to save "Subgraphs", we might want to auto-extract prompts.
        # TODO: Implement auto-extraction of long strings > 100 chars to assets/?
        
        # 3. Save YAML
        with open(os.path.join(bundle_path, "graph.yaml"), 'w', encoding='utf-8') as f:
            yaml.safe_dump(graph_def, f, sort_keys=False, allow_unicode=True)

    @staticmethod
    def _resolve_assets(data: Any, root_path: str):
        """Recursively resolve file:// references in the dictionary."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and value.startswith("file://"):
                    # Load file
                    rel_path = value.replace("file://", "")
                    # Security check: prevent ../ traversal out of bundle? 
                    # For now assume trusted content.
                    full_path = os.path.join(root_path, rel_path)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            data[key] = f.read()
                    except Exception as e:
                        print(f"Warning: Failed to load asset {full_path}: {e}")
                else:
                    GraphBundle._resolve_assets(value, root_path)
        elif isinstance(data, list):
            for item in data:
                GraphBundle._resolve_assets(item, root_path)
