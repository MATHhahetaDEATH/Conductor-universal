from __future__ import annotations
import threading
import logging
import os
from typing import Any, Callable, Dict, Tuple, List, Optional

from .command.node import AbstractNode
from .permission import PermissionLevel, CommandSource
from .events import EventDispatcher, _DECORATED_LISTENERS
from .plugin_manager import PluginManager
from .dependencies import DependencyManager
from .log_system import SystemLogService
from .user_manager import UserManager

logger = logging.getLogger("conductor.kernel")

class Kernel:
    """The core engine of the Conductor system."""

    def __init__(self, plugin_dirs: list[str], storage_dir: str = "storage", debug: bool = False) -> None:
        self.logger = logger
        self.debug = debug
        self.events = EventDispatcher()
        self.storage_dir = os.path.abspath(storage_dir)
        self.logs_dir = os.path.join(self.storage_dir, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)

        from .logging_helper import ConductorLogManager
        self.logs = ConductorLogManager(self.logs_dir, logging.DEBUG if debug else logging.INFO)
        self.logs.configure_root()
        self.system_web_routes: list[dict] = []
        self.log_system = SystemLogService(self)
        
        self.plugins = PluginManager(self, plugin_dirs)
        webapp_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "WebApp"))
        self.dependencies = DependencyManager(webapp_base, plugin_dirs)
        self.users = UserManager(self.storage_dir)
        
        # Command Tree Root
        self._command_root = AbstractNode()
        
        # Web Blueprint Registration
        self._blueprints = []
        
        # Shutdown coordination
        self.shutdown_event = threading.Event()
        self._debug_watcher_thread: Optional[threading.Thread] = None

    def get_plugin_storage_path(self, plugin_id: str, sub_dir: str = "") -> str:
        """Get the absolute path to a plugin's dedicated storage directory."""
        path = os.path.join(self.storage_dir, sub_dir, plugin_id)
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return path

    def get_plugin_config_dir(self, plugin_id: str) -> str:
        """Helper to get the configuration directory for a plugin."""
        return self.get_plugin_storage_path(plugin_id, "config")

    def get_plugin_data_dir(self, plugin_id: str) -> str:
        """Helper to get the data directory for a plugin."""
        return self.get_plugin_storage_path(plugin_id, "data")

    def get_logger(self, plugin_id: str) -> logging.LoggerAdapter:
        """Get a logger adapter that automatically tags logs with the plugin_id."""
        plugin_logger = logging.getLogger(f"conductor.plugins.{plugin_id}")
        return logging.LoggerAdapter(plugin_logger, {"plugin_id": plugin_id})

    def register_event_listener(self, event_id: str, callback: Callable, priority: int = 1000, plugin_id: str = "core") -> None:
        """Register a callback for a specific event."""
        self.events.register_listener(event_id, callback, priority, plugin_id)

    def remove_listeners_by_plugin(self, plugin_id: str) -> int:
        """Remove all listeners registered by a specific plugin."""
        return self.events.remove_listeners_by_plugin(plugin_id)

    def dispatch_event(self, event_id: str, *args: Any, **kwargs: Any) -> None:
        """Dispatch an event to all registered listeners."""
        self.events.dispatch(event_id, *args, **kwargs)

    def register_command(self, trigger: str, callback: Callable, permission: int = PermissionLevel.USER, 
                         description: str = "", plugin_id: str = "core") -> None:
        """
        Convenient helper to register a command from a simple string template (MCDR style).
        Example: kernel.register_command("!!claw ping", my_callback, PermissionLevel.OWNER)
        """
        from .command.builder import SimpleCommandBuilder
        builder = SimpleCommandBuilder()
        builder.command(trigger, callback, permission, description, plugin_id)
        builder.register(self)

    def register_command_node(self, node: AbstractNode) -> None:
        """Attach a command node tree to the kernel's root, merging branches recursively."""
        self._command_root.merge_child(node)
        logger.debug(f"Registered/Merged command node at root: {getattr(node, 'literal', node.__class__.__name__)}")

    def register_blueprint(self, blueprint, url_prefix: str = "") -> None:
        """Register a Flask Blueprint for Web API expansion."""
        self._blueprints = [
            (bp, prefix) for bp, prefix in self._blueprints
            if not (bp.name == blueprint.name and prefix == url_prefix)
        ]
        self._blueprints.append((blueprint, url_prefix))
        logger.debug(f"Registered Blueprint: {blueprint.name} at {url_prefix}")

    def remove_commands_by_plugin(self, plugin_id: str) -> int:
        """Recursively remove all commands registered by a specific plugin."""
        def _remove_recursive(node: AbstractNode) -> int:
            count = 0
            # Remove callback if it belongs to plugin
            if node.plugin_id == plugin_id and node.callback:
                node.callback = None
                count += 1
            # Recurse and remove dead branches
            alive_children = []
            for child in node.children:
                count += _remove_recursive(child)
                # Keep if it has children or a callback
                if child.children or child.callback:
                    alive_children.append(child)
            node.children = alive_children
            return count
            
        removed = _remove_recursive(self._command_root)
        if removed > 0:
            logger.debug(f"Removed {removed} commands for plugin '{plugin_id}'")
        return removed

    def execute_command(self, source: CommandSource, text: str) -> bool:
        """Attempt to execute a registered command by traversing the command tree."""
        parts = text.split()
        if not parts:
            return False
            
        # Parse against the root's children
        for child in self._command_root.children:
            executables = child.get_executable_nodes(parts, {})
            if executables:
                # Execute the first matching fully parsed branch
                target_node, context = executables[0]
                
                # Permission check
                if source.permission_level < target_node.permission_level:
                    source.reply(f"Error: Permission denied. Required: {PermissionLevel(target_node.permission_level).name}", plugin_id="core")
                    return False
                
                try:
                    class BoundCommandSource(CommandSource):
                        def reply(self, msg: str, plugin_id: str = target_node.plugin_id):
                            source.reply(msg, plugin_id=plugin_id)
                            
                    bound_source = BoundCommandSource(source.name, source.permission_level)
                    target_node.callback(bound_source, context)
                    return True
                except Exception as e:
                    logger.error(f"Error executing command: {e}", exc_info=True)
                    source.reply(f"Command Error: {e}", plugin_id="core")
                    return False
        
        source.reply("Unknown command or invalid arguments. Type !!conductor help to view commands.", plugin_id="core")
        return False
        
    def generate_suggestions(self, text: str) -> list[str]:
        """Generate auto-completion suggestions for the given input string."""
        # Simple split, but keep the trailing empty string if user typed a space
        parts = [p for p in text.split(" ")]
        # If the input is completely empty, suggest base literals
        if not parts:
            parts = [""]
            
        suggestions = []
        for child in self._command_root.children:
            suggestions.extend(child.generate_suggestions(parts))
        
        # Deduplicate while preserving order
        return list(dict.fromkeys(suggestions))
        
    def get_all_commands(self) -> list[dict]:
        """Utility for help and debug to get all flattened command strings."""
        commands = []
        def _flatten(node: AbstractNode, path: list[str]):
            # Construct path string
            name = getattr(node, 'literal', None) or (f"<{getattr(node, 'name', '?')}>" if hasattr(node, 'name') else "")
            new_path = path + [name] if name else path
            
            if node.callback:
                commands.append({
                    "trigger": " ".join(new_path),
                    "permission": node.permission_level,
                    "description": node.description,
                    "plugin_id": node.plugin_id
                })
            for child in node.children:
                _flatten(child, new_path)
                
        for child in self._command_root.children:
            _flatten(child, [])
        return commands

    def start(self) -> None:
        """Initialize the kernel, load plugins, and start operations."""
        logger.info("Starting Conductor Kernel...")
        self.log_system.register()

        # Register decorator-based listeners
        for event_id, priority, func in _DECORATED_LISTENERS:
            self.register_event_listener(event_id, func, priority)

        # Load plugins
        self.plugins.load_all()

        # Fire startup event
        self.dispatch_event("conductor.kernel_start", self)
        if self.debug:
            self._start_debug_watcher()
        logger.info("Kernel started successfully.")

    def _start_debug_watcher(self) -> None:
        """Start a lightweight plugin file watcher for debug hot reload."""
        if self._debug_watcher_thread and self._debug_watcher_thread.is_alive():
            return

        def watch() -> None:
            logger.info("Debug plugin watcher started.")
            while not self.shutdown_event.wait(1.0):
                for plugin_id in self.plugins.get_changed_plugins():
                    logger.info(f"Debug reload triggered by file change in plugin '{plugin_id}'.")
                    try:
                        self.plugins.reload_plugin(plugin_id)
                    except Exception as e:
                        logger.error(f"Debug reload failed for '{plugin_id}': {e}", exc_info=True)

        self._debug_watcher_thread = threading.Thread(target=watch, daemon=True)
        self._debug_watcher_thread.start()

    def stop(self) -> None:
        """Gracefully shut down the kernel."""
        logger.info("Stopping Conductor Kernel...")
        self.shutdown_event.set()
        self.dispatch_event("conductor.kernel_stop", self)
        logger.info("Kernel stopped.")
        self.logs.close()
