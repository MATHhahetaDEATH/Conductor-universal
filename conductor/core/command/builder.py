from typing import Any, Callable, Dict, Type
from .node import AbstractNode, Literal, Text

class SimpleCommandBuilder:
    """A helper class to construct Command Trees from string templates (MCDR style)."""
    
    def __init__(self):
        # We hold a dummy root node that groups all commands built by this builder.
        self.root = AbstractNode()
        self.arg_types: Dict[str, Type[AbstractNode]] = {}

    def arg(self, name: str, node_type: Type[AbstractNode]) -> 'SimpleCommandBuilder':
        """Specify the node type for an argument."""
        self.arg_types[name] = node_type
        return self

    def command(self, template: str, callback: Callable, permission: int = 1, desc: str = "", plugin_id: str = "core") -> 'SimpleCommandBuilder':
        """
        Parse a template string and insert it into the tree.
        Example: '!!process analyze <source_id>'
        """
        parts = template.strip().split()
        if not parts:
            return self

        current_nodes = [self.root]

        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)
            
            # Check if part is an argument <arg_name> or greedy <<arg_name>>
            if part.startswith("<<") and part.endswith(">>"):
                arg_name = part[2:-2]
                from .node import GreedyText
                new_node = GreedyText(arg_name)
            elif part.startswith("<") and part.endswith(">"):
                arg_name = part[1:-1]
                node_type = self.arg_types.get(arg_name, Text)
                new_node = node_type(arg_name)
            else:
                new_node = Literal(part)

            next_nodes = []
            for current_node in current_nodes:
                # See if a child of this type/value already exists to share the tree path
                existing_child = None
                new_id = new_node.get_id()
                for child in current_node.children:
                    if type(child) == type(new_node) and child.get_id() == new_id:
                        existing_child = child
                        break
                
                if existing_child:
                    child_node = existing_child
                else:
                    child_node = current_node.extends(new_node)
                
                if is_last:
                    child_node.runs(callback, permission, desc, plugin_id)
                    
                next_nodes.append(child_node)
                
            current_nodes = next_nodes
            
        return self

    def register(self, kernel: Any) -> None:
        """Register all built trees to the kernel."""
        # The kernel will extract the top-level children from our dummy root 
        # and attach them to its own root registry.
        for child in self.root.children:
            kernel.register_command_node(child)
