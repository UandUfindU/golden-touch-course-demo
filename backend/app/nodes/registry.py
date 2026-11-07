from typing import Dict, Type, List, Optional
from app.nodes.base import BaseNode
import inspect
from app.core.enums import NodeCategory, NodeScope, NodeRole

class NodeRegistry:
    _nodes: Dict[str, Type[BaseNode]] = {}
    _metadata: Dict[str, Dict] = {}

    @classmethod
    def register(cls, category: NodeCategory, name: str, scopes: List[NodeScope] = [NodeScope.STRATEGY], role: Optional["NodeRole"] = None):
        """Decorator to register a node implementation"""
        def wrapper(node_cls: Type[BaseNode]):
            if not issubclass(node_cls, BaseNode):
                raise ValueError(f"Class {node_cls} must inherit from BaseNode")
            
            # Generate unique key (e.g., "process.clean_data")
            # For now using name as key, but ideally should be scoped
            unique_key = name  
            
            if unique_key in cls._nodes:
                # Warning: Overwriting existing node. This is acceptable during development/reloads.
                print(f"WARNING: Node {unique_key} already registered. Overwriting.")
                # Don't raise, just overwrite.
                # raise ValueError(f"Node {unique_key} already registered")

            # Inject metadata into class
            node_cls.category = category
            
            cls._nodes[unique_key] = node_cls
            cls._metadata[unique_key] = {
                "name": name,
                "category": category,
                "scopes": scopes,
                "role": role,  # Added role to metadata
                "description": node_cls.description,
                "input_schema": node_cls.get_input_schema_json(),
                "output_schema": node_cls.get_output_schema_json(),
                "class_path": f"{node_cls.__module__}.{node_cls.__name__}"
            }
            return node_cls
        return wrapper

    @classmethod
    def get_node(cls, name: str) -> Type[BaseNode]:
        if name not in cls._nodes:
            raise ValueError(f"Node {name} not found")
        return cls._nodes[name]

    @classmethod
    def get_all_metadata(cls) -> List[Dict]:
        return list(cls._metadata.values())

# Global instance
registry = NodeRegistry
register_node = NodeRegistry.register
