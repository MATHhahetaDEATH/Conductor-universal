from typing import Any, Callable, Dict, List, Optional, Tuple

class AbstractNode:
    """Base class for all command tree nodes."""
    def __init__(self):
        self.children: List['AbstractNode'] = []
        self.callback: Optional[Callable] = None
        self.permission_level: int = 1 # USER
        self.plugin_id: str = "core"
        # Optional string to describe the node path to this point
        self.description: str = ""

    def extends(self, node: 'AbstractNode') -> 'AbstractNode':
        """Add a child node and return the child for chaining."""
        self.children.append(node)
        return node
        
    def runs(self, callback: Callable, permission: int = 1, desc: str = "", plugin_id: str = "core") -> 'AbstractNode':
        """Set the executable callback for this node."""
        self.callback = callback
        self.permission_level = permission
        self.description = desc
        self.plugin_id = plugin_id
        return self

    def get_id(self) -> str:
        """Return a unique identifier for merging nodes of the same type/value."""
        return ""

    def merge_child(self, new_node: 'AbstractNode') -> None:
        """Recursively merge a new node (and its subtree) into this node's children."""
        existing = None
        new_node_id = new_node.get_id()
        
        for child in self.children:
            if type(child) == type(new_node) and child.get_id() == new_node_id:
                existing = child
                break
        
        if existing:
            # Recursive merge children
            for sub_child in new_node.children:
                existing.merge_child(sub_child)
            # Update callback if the new node has one
            if new_node.callback:
                existing.runs(new_node.callback, new_node.permission_level, new_node.description, new_node.plugin_id)
        else:
            self.extends(new_node)

    def parse(self, args: List[str], ctx: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Attempt to parse the current argument.
        Returns: (Success, Remaining Args, Updated Context)
        """
        raise NotImplementedError

    def generate_suggestions(self, args: List[str]) -> List[str]:
        """
        Recursively generate suggestions for the current input.
        """
        if not args:
            return []

        word = args[0]
        
        # If this is the last word the user is typing, generate suggestions for THIS node
        if len(args) == 1:
            return [s for s in self.get_suggestions() if s.startswith(word)]
            
        # If not the last word, we must fully match this node to proceed to children
        success, remaining, _ = self.parse(args, {})
        if success:
            suggests = []
            for child in self.children:
                suggests.extend(child.generate_suggestions(remaining))
            return suggests
            
        return []

    def get_suggestions(self) -> List[str]:
        """Return the possible fully-typed values for this node."""
        return []

    def get_executable_nodes(self, args: List[str], ctx: Dict[str, Any]) -> List[Tuple['AbstractNode', Dict[str, Any]]]:
        """
        Parse args and return all nodes that match the input AND have a callback.
        This handles cases where multiple branches might match (though unusual).
        """
        if not args:
            return [(self, ctx)] if self.callback else []

        success, remaining, new_ctx = self.parse(args, ctx.copy())
        if not success:
            return []

        if not remaining:
            # Fully parsed all input
            return [(self, new_ctx)] if self.callback else []

        results = []
        for child in self.children:
            results.extend(child.get_executable_nodes(remaining, new_ctx))
        return results

class Literal(AbstractNode):
    """A node that matches an exact string."""
    def __init__(self, literal: str):
        super().__init__()
        self.literal = literal

    def parse(self, args: List[str], ctx: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        if args and args[0] == self.literal:
            return True, args[1:], ctx
        return False, args, ctx

    def get_suggestions(self) -> List[str]:
        return [self.literal]

    def get_id(self) -> str:
        return self.literal

class Text(AbstractNode):
    """A node that captures any string into the context."""
    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def parse(self, args: List[str], ctx: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        if args:
            ctx[self.name] = args[0]
            return True, args[1:], ctx
        return False, args, ctx

    def get_suggestions(self) -> List[str]:
        # Text fields generally don't have predefined suggestions unless subclassed
        return [f"<{self.name}>"]

    def get_id(self) -> str:
        return self.name
        
class Integer(AbstractNode):
    """A node that matches and parses an integer."""
    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def parse(self, args: List[str], ctx: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        if args:
            try:
                val = int(args[0])
                ctx[self.name] = val
                return True, args[1:], ctx
            except ValueError:
                pass
        return False, args, ctx

    def get_suggestions(self) -> List[str]:
        return [f"<{self.name}:int>"]

    def get_id(self) -> str:
        return self.name

class GreedyText(AbstractNode):
    """A node that captures all remaining arguments into the context as a list."""
    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def parse(self, args: List[str], ctx: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        if args:
            ctx[self.name] = args
            return True, [], ctx # Consumes everything
        return False, args, ctx

    def get_suggestions(self) -> List[str]:
        return [f"<{self.name}...>"]

    def get_id(self) -> str:
        return self.name
