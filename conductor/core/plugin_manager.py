from __future__ import annotations
import importlib.util
import importlib
import logging
import os
import sys
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from conductor.core.events import _DECORATED_LISTENERS

logger = logging.getLogger("conductor.plugins")

class PluginManager:
    """Manages the discovery, loading, and lifecycle of plugins."""

    def __init__(self, kernel: Any, plugin_dirs: list[str]) -> None:
        self.kernel = kernel
        self.plugin_dirs = plugin_dirs
        self.loaded_plugins: Dict[str, Any] = {}
        # Map plugin_id -> filepath for reloading
        self.plugin_file_map: Dict[str, str] = {}
        # Map plugin_id -> is_core status
        self.plugin_is_core_map: Dict[str, bool] = {}
        # Store dynamic web routes to be written to the manifest
        self.web_routes: list[Dict[str, Any]] = []
        self.plugin_file_mtimes: Dict[str, Dict[str, float]] = {}
        
        # Topology data
        self.plugin_candidates: list[dict] = []
        self.dependency_edges: list[list[str]] = []
        
        # Base paths for WebApp integration
        self.webapp_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "WebApp"))
        self.webapp_pages = os.path.join(self.webapp_base, "src", "pages", "plugins")
        self.webapp_routes_file = os.path.join(self.webapp_base, "src", "plugin_routes.ts")

    def load_all(self) -> None:
        """Discover, sort by dependencies/priority, and load all plugins."""
        candidates = []

        try:
            self.kernel.dependencies.scan_plugin_dirs()
            sync_result = self.kernel.dependencies.sync_manifests("all")
            added = [
                f"{change['ecosystem']}:{dep['name']}"
                for change in sync_result.get("changes", [])
                for dep in change.get("added", [])
            ]
            if added:
                logger.info(f"Synchronized plugin dependencies into project manifests: {', '.join(added)}")
            if os.environ.get("CONDUCTOR_AUTO_INSTALL_PLUGIN_DEPS", "1").lower() not in {"0", "false", "no", "off"}:
                install_result = self.kernel.dependencies.ensure_project_dependencies("python", install=True)
                for command in install_result.get("commands", []):
                    if command.get("returncode") == 0:
                        logger.info(f"Plugin Python dependencies are installed via: {' '.join(command.get('command', []))}")
                    else:
                        logger.warning(
                            f"Plugin Python dependency install failed via {' '.join(command.get('command', []))}: "
                            f"{command.get('stderr', '').strip()}"
                        )
        except Exception as e:
            logger.warning(f"Failed to synchronize plugin dependency manifests: {e}", exc_info=True)
        
        # Ensure target directory exists and is clean
        if os.path.exists(self.webapp_pages):
            shutil.rmtree(self.webapp_pages)
        os.makedirs(self.webapp_pages, exist_ok=True)
        self.web_routes = []
        self.plugin_file_mtimes = {}
        self.plugin_candidates = []
        self.dependency_edges = []

        # Phase 1: Discovery & Pre-import (without calling on_load)
        for pdir in self.plugin_dirs:
            if not os.path.exists(pdir):
                logger.warning(f"Plugin directory not found: {pdir}")
                continue

            is_core_dir = "core" in os.path.abspath(pdir).split(os.sep)
            
            for item in sorted(os.listdir(pdir)):
                if item.startswith("__"): continue
                item_path = os.path.join(pdir, item)
                
                # Check for single-file or directory package
                valid = False
                if item.endswith(".py") and os.path.isfile(item_path):
                    valid = True
                elif os.path.isdir(item_path) and os.path.isfile(os.path.join(item_path, "__init__.py")):
                    valid = True
                
                if valid:
                    plugin_info = self._pre_load_module(item_path, is_core_dir)
                    if plugin_info:
                        candidates.append(plugin_info)

        # Phase 2: Topological Sort (Dependencies + Priority)
        sorted_plugins = self._resolve_loading_order(candidates)

        # Phase 3: Formal Initialization (Call on_load)
        for p in sorted_plugins:
            self._initialize_plugin(p)
            
        # Phase 4: Write Route Manifest
        self._write_web_route_manifest()

    def _write_web_route_manifest(self) -> None:
        """Generate and write the WebApp route manifest file."""
        core_routes = [
            {"path": "/core/plugin-management", "key": "core/plugin-management", "name": "Core Plugin Management", "icon": "api", "component": "core/plugin-management", "hideInMenu": False, "is_core": True},
            {"path": "/core/terminal", "key": "core/terminal", "name": "Core Web Terminal", "icon": "code", "component": "core/web-terminal", "hideInMenu": False, "is_core": True},
        ]
        routes = core_routes + [route for route in self.web_routes if route.get("path") not in {item["path"] for item in core_routes}]
        content = "/**\n * @name Plugin dynamic routes\n * @description This file is automatically generated by Conductor PluginManager.\n * DO NOT EDIT MANUALLY.\n */\n\nexport default "
        content += json.dumps(routes, indent=2)
        content += ";\n"
        
        try:
            with open(self.webapp_routes_file, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Updated WebApp route manifest with {len(self.web_routes)} routes.")
        except Exception as e:
            logger.error(f"Failed to write WebApp route manifest: {e}")

    def _remove_web_routes_for_plugin(self, plugin_id: str) -> None:
        """Remove manifest routes owned by a plugin before reload/unload."""
        owned_components = {
            f"plugins/{plugin_id}",
            f"plugins/{plugin_id}_wrapper",
            f"plugins/{plugin_id}_html_wrapper",
            f"./plugins/{plugin_id}",
            f"./plugins/{plugin_id}_wrapper",
            f"./plugins/{plugin_id}_html_wrapper",
        }
        owned_paths = {
            f"/{plugin_id}",
            f"/plugins/{plugin_id}",
            f"/{plugin_id}/html",
            f"/plugins/{plugin_id}/html",
        }

        self.web_routes = [
            route for route in self.web_routes
            if route.get("component") not in owned_components and route.get("path") not in owned_paths
        ]

    def _clear_webapp_page_target(self, plugin_id: str) -> None:
        """Clear generated WebApp page entries for a plugin before deploying."""
        targets = [
            os.path.join(self.webapp_pages, plugin_id),
            os.path.join(self.webapp_pages, f"{plugin_id}.tsx"),
            os.path.join(self.webapp_pages, f"{plugin_id}_wrapper.tsx"),
            os.path.join(self.webapp_pages, f"{plugin_id}_html_wrapper.tsx"),
        ]
        for target in targets:
            if os.path.islink(target) or os.path.isfile(target):
                os.unlink(target)
            elif os.path.isdir(target):
                shutil.rmtree(target)

    def _refresh_web_symlink(self, source_path: str, target_path: str) -> None:
        """Recreate a symlink so frontend watchers can observe plugin reloads."""
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        os.symlink(source_path, target_path, target_is_directory=os.path.isdir(source_path))

    def _initialize_plugin(self, p: dict, prev_module: Any = None) -> None:
        """Call on_load and finalize plugin loading."""
        pid = p["id"]
        module = p["module"]
        metadata = p["metadata"]
        plugin_path = p["path"]

        # Register declared dependencies before on_load so missing runtime packages
        # remain visible even if plugin initialization fails.
        self.kernel.dependencies.update_plugin(pid, plugin_path)

        # Register listeners captured during discovery
        for event_id, priority, func in p["listeners"]:
            self.kernel.register_event_listener(event_id, func, priority, pid)

        on_load = getattr(module, "on_load", None)
        if callable(on_load):
            logger.info(f"Loading plugin: {metadata.get('name', pid)} (v{metadata.get('version', 'unknown')})")
            self.kernel.get_plugin_config_dir(pid)
            self.kernel.get_plugin_data_dir(pid)
            previous_logger = self.kernel.logger
            previous_blueprints = list(getattr(self.kernel, "_blueprints", []))
            self.kernel.logger = self.kernel.get_logger(pid)
            try:
                on_load(self.kernel, prev_module)
            except Exception:
                logger.error(f"Error during on_load for '{pid}'.", exc_info=True)
                if hasattr(self.kernel, "_blueprints"):
                    self.kernel._blueprints = previous_blueprints
                self.kernel.remove_listeners_by_plugin(pid)
                self.kernel.remove_commands_by_plugin(pid)
                self.kernel.dependencies.remove_plugin(pid)
                self._remove_web_routes_for_plugin(pid)
                raise
            finally:
                self.kernel.logger = previous_logger
        
        self.loaded_plugins[pid] = module
        self.plugin_file_map[pid] = p["path"]
        self.plugin_is_core_map[pid] = p.get("is_core", False)
        
        # Handle Web UI assets
        self._deploy_web_ui(pid, plugin_path, metadata)
        self._snapshot_plugin_files(pid, plugin_path)
        
        logger.debug(f"Plugin '{pid}' fully initialized.")

    def _deploy_web_ui(self, pid: str, plugin_path: str, metadata: dict) -> None:
        """Handle symlinking web assets and registering dynamic routes."""
        if not os.path.isdir(plugin_path):
            return
            
        web_dir = os.path.join(plugin_path, "web")
        if not os.path.exists(web_dir):
            return
            
        # Target path in WebApp
        target_dir = os.path.join(self.webapp_pages, pid)
        is_core = self.plugin_is_core_map.get(pid, False)
        
        try:
            # Identify UI type and register route
            has_tsx = os.path.exists(os.path.join(web_dir, "index.tsx"))
            has_html = os.path.exists(os.path.join(web_dir, "index.html"))
            
            # Add extra routes if defined
            extra_routes = metadata.get("web_extra_routes", [])
            if isinstance(extra_routes, list):
                for route in extra_routes:
                    # Enforce component path safety if needed, but for now trust metadata
                    if "path" in route and "key" not in route:
                        route["key"] = route["path"].lstrip("/")
                    if "is_core" not in route:
                        route["is_core"] = is_core
                    # Clean up component path
                    if "component" in route and isinstance(route["component"], str):
                        if route["component"].startswith("./"):
                            route["component"] = route["component"][2:]
                    self.web_routes.append(route)

            # Native TSX Route
            if is_core:
                route_path = f"/{pid}"
            else:
                route_path = f"/plugins/{pid}"

            if has_tsx:
                os.makedirs(target_dir, exist_ok=True)
                source_names = {
                    item for item in os.listdir(web_dir)
                    if item != "index.html" and not item.startswith(".")
                }
                for item in source_names:
                    if item == "index.html":
                        continue
                    source_path = os.path.join(web_dir, item)
                    target_path = os.path.join(target_dir, item)
                    if os.path.lexists(target_path):
                        if os.path.isdir(target_path) and not os.path.islink(target_path):
                            shutil.rmtree(target_path)
                        else:
                            os.unlink(target_path)
                    self._refresh_web_symlink(source_path, target_path)
                for item in os.listdir(target_dir):
                    if item not in source_names:
                        stale_path = os.path.join(target_dir, item)
                        if os.path.isdir(stale_path) and not os.path.islink(stale_path):
                            shutil.rmtree(stale_path)
                        else:
                            os.unlink(stale_path)
                logger.info(f"Refreshed native web UI symlinks for plugin '{pid}' in WebApp.")

                self.web_routes.append({
                    "path": route_path,
                    "key": route_path.lstrip("/"),
                    "name": metadata.get("web_name", pid),
                    "icon": metadata.get("web_icon", "api"),
                    "component": f"plugins/{pid}",
                    "hideInMenu": metadata.get("web_hide_in_menu", False),
                    "is_core": is_core
                })

            if has_html:
                if not has_tsx:
                    self._clear_webapp_page_target(pid)
                wrapper_suffix = "_html_wrapper" if has_tsx else "_wrapper"
                wrapper_component = f"plugins/{pid}{wrapper_suffix}"
                html_route_path = f"{route_path}/html" if has_tsx else route_path
                html_route_name = f"{metadata.get('web_name', pid)} HTML" if has_tsx else metadata.get("web_name", pid)

                # HTML Iframe Wrapper Route (Dynamic Wrapper)
                reload_token = int(time.time() * 1000)
                wrapper_content = f"""import React from 'react';
import PluginWrapper from '@/components/PluginWrapper';

const {pid.capitalize()}HtmlPlugin: React.FC = () => {{
  return <PluginWrapper url="/api/static/plugins/{pid}/index.html?v={reload_token}" />;
}};

export default {pid.capitalize()}HtmlPlugin;
"""
                wrapper_path = os.path.join(self.webapp_pages, f"{pid}{wrapper_suffix}.tsx")
                with open(wrapper_path, "w", encoding="utf-8") as f:
                    f.write(wrapper_content)
                    
                self.web_routes.append({
                    "path": html_route_path,
                    "key": html_route_path.lstrip("/"),
                    "name": html_route_name,
                    "icon": metadata.get("web_icon", "api"),
                    "component": wrapper_component,
                    "hideInMenu": True if has_tsx else metadata.get("web_hide_in_menu", False),
                    "is_core": is_core
                })
        except Exception as e:
            logger.error(f"Failed to deploy web UI for plugin '{pid}': {e}")

    def _snapshot_plugin_files(self, plugin_id: str, plugin_path: str) -> None:
        """Record mtimes for source and web files used by debug hot reload."""
        watched_suffixes = {".py", ".tsx", ".ts", ".html", ".css", ".less", ".json"}
        mtimes: Dict[str, float] = {}

        if os.path.isfile(plugin_path):
            files = [Path(plugin_path)]
        elif os.path.isdir(plugin_path):
            files = [
                path for path in Path(plugin_path).rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            ]
        else:
            files = []

        for path in files:
            if path.suffix not in watched_suffixes:
                continue
            try:
                mtimes[str(path)] = path.stat().st_mtime
            except OSError:
                continue

        self.plugin_file_mtimes[plugin_id] = mtimes

    def get_changed_plugins(self) -> list[str]:
        """Return plugin IDs whose watched files changed since the last snapshot."""
        changed = []
        for plugin_id, plugin_path in list(self.plugin_file_map.items()):
            previous = self.plugin_file_mtimes.get(plugin_id, {})
            self._snapshot_plugin_files(plugin_id, plugin_path)
            current = self.plugin_file_mtimes.get(plugin_id, {})
            if previous and current != previous:
                changed.append(plugin_id)
        return changed

    def _pre_load_module(self, path: str, is_core: bool) -> Optional[dict]:
        """Execute top-level code and extract metadata/listeners without starting the plugin."""
        if os.path.isdir(path):
            actual_filepath = os.path.join(path, "__init__.py")
            plugin_name = os.path.basename(path)
        else:
            actual_filepath = path
            plugin_name = os.path.splitext(os.path.basename(path))[0]

        try:
            _DECORATED_LISTENERS.clear()
            spec = importlib.util.spec_from_file_location(plugin_name, actual_filepath)
            if not (spec and spec.loader): return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[plugin_name] = module
            spec.loader.exec_module(module)

            metadata = getattr(module, "PLUGIN_METADATA", None)
            if not (metadata and isinstance(metadata, dict)):
                logger.debug(f"Ignored '{plugin_name}': Missing PLUGIN_METADATA.")
                return None

            plugin_id = metadata.get("id", plugin_name)
            
            # Capture listeners
            listeners = list(_DECORATED_LISTENERS)
            _DECORATED_LISTENERS.clear()

            return {
                "id": plugin_id,
                "module": module,
                "metadata": metadata,
                "path": path,
                "is_core": is_core,
                "listeners": listeners,
                "dependencies": metadata.get("dependencies", []),
                "priority": metadata.get("priority", 0)
            }
        except Exception as e:
            logger.error(f"Discovery error {path}: {e}", exc_info=True)
            return None

    def _resolve_loading_order(self, candidates: list[dict]) -> list[dict]:
        """Strictly order plugins: Core first, then resolve dependencies, then Alpha."""
        id_map = {p["id"]: p for p in candidates}
        
        # Build graph
        adj = {p["id"]: [] for p in candidates}
        in_degree = {p["id"]: 0 for p in candidates}
        
        for p in candidates:
            for dep in p["dependencies"]:
                if dep not in id_map:
                    raise RuntimeError(f"Plugin '{p['id']}' requires missing dependency '{dep}'")
                adj[dep].append(p["id"])
                in_degree[p["id"]] += 1
                self.dependency_edges.append([dep, p["id"]])
        
        self.plugin_candidates = candidates

        # Sort candidates for tie-breaking: is_core desc, then id asc
        # This ensures among 0-in-degree nodes, core plugins are picked first
        queue = [p["id"] for p in candidates if in_degree[p["id"]] == 0]
        
        def sort_key(pid):
            p = id_map[pid]
            # Higher priority fires first (-priority for ascending heap), then core (False<True), then alphabetical.
            return (-p["priority"], 0 if p["is_core"] else 1, p["id"])

        sorted_ids = []
        while queue:
            queue.sort(key=sort_key)
            current_id = queue.pop(0)
            sorted_ids.append(current_id)
            
            for neighbor in adj[current_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_ids) != len(candidates):
            cycle_ids = set(id_map.keys()) - set(sorted_ids)
            raise RuntimeError(f"Circular dependency detected among plugins: {cycle_ids}")

        return [id_map[pid] for pid in sorted_ids]

    def load_plugin(self, path: str, prev_module: Any = None, write_manifest: bool = True) -> bool:
        """Load a single plugin bypass (used for manual loading/reloading)."""
        # For simplicity, during manual load we just perform core identification and init
        is_core = "core" in os.path.abspath(path).split(os.sep)
        p = self._pre_load_module(path, is_core)
        if p:
            self._initialize_plugin(p, prev_module=prev_module)
            if write_manifest:
                self._write_web_route_manifest()
            return True
        return False

    def _get_dependent_closure(self, plugin_id: str) -> set[str]:
        """Return loaded plugins that directly or indirectly depend on plugin_id."""
        dependents: dict[str, set[str]] = {pid: set() for pid in self.loaded_plugins}
        for pid, module in self.loaded_plugins.items():
            metadata = getattr(module, "PLUGIN_METADATA", {})
            for dependency in metadata.get("dependencies", []):
                dependents.setdefault(dependency, set()).add(pid)

        closure: set[str] = set()
        stack = list(dependents.get(plugin_id, set()))
        while stack:
            current = stack.pop()
            if current in closure:
                continue
            closure.add(current)
            stack.extend(dependents.get(current, set()))
        return closure

    def _sort_loaded_subset(self, plugin_ids: set[str]) -> list[str]:
        """Topologically sort a loaded plugin subset using current metadata."""
        info = {}
        for pid in plugin_ids:
            module = self.loaded_plugins.get(pid)
            if not module:
                continue
            metadata = getattr(module, "PLUGIN_METADATA", {})
            info[pid] = {
                "dependencies": [dep for dep in metadata.get("dependencies", []) if dep in plugin_ids],
                "priority": metadata.get("priority", 0),
                "is_core": self.plugin_is_core_map.get(pid, False),
            }

        adjacency = {pid: [] for pid in info}
        in_degree = {pid: 0 for pid in info}
        for pid, item in info.items():
            for dependency in item["dependencies"]:
                adjacency[dependency].append(pid)
                in_degree[pid] += 1

        queue = [pid for pid in info if in_degree[pid] == 0]

        def sort_key(pid: str):
            item = info[pid]
            return (-item["priority"], 0 if item["is_core"] else 1, pid)

        sorted_ids = []
        while queue:
            queue.sort(key=sort_key)
            current = queue.pop(0)
            sorted_ids.append(current)
            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_ids) != len(info):
            raise RuntimeError(f"Circular dependency detected while reloading plugins: {set(info) - set(sorted_ids)}")
        return sorted_ids

    def _get_loaded_suffix_chain(self, plugin_id: str) -> list[str]:
        """Return plugin_id and everything after it in the canonical loaded order."""
        ordered = self._sort_loaded_subset(set(self.loaded_plugins))
        if plugin_id not in ordered:
            return []
        return ordered[ordered.index(plugin_id):]

    def unload_plugin(self, plugin_id: str, write_manifest: bool = True) -> bool:
        """Unload a plugin and remove its registered resources."""
        if plugin_id not in self.loaded_plugins:
            logger.warning(f"Plugin '{plugin_id}' is not loaded.")
            return False

        module = self.loaded_plugins[plugin_id]
        on_unload = getattr(module, "on_unload", None)
        if callable(on_unload):
            try:
                on_unload(self.kernel)
            except Exception as e:
                logger.error(f"Error during on_unload for '{plugin_id}': {e}")

        self.kernel.remove_listeners_by_plugin(plugin_id)
        self.kernel.remove_commands_by_plugin(plugin_id)
        self.kernel.dependencies.remove_plugin(plugin_id)
        self._remove_web_routes_for_plugin(plugin_id)
        del self.loaded_plugins[plugin_id]
        if write_manifest:
            self._write_web_route_manifest()
        logger.info(f"Plugin '{plugin_id}' unloaded.")
        return True

    def _reload_plugin_single(self, plugin_id: str) -> bool:
        """Reload one plugin without touching dependents."""
        filepath = self.plugin_file_map.get(plugin_id)
        if not filepath:
            logger.error(f"Cannot reload '{plugin_id}': Source file location unknown.")
            return False

        previous_module = self.loaded_plugins.get(plugin_id)
        self.unload_plugin(plugin_id, write_manifest=False)
        try:
            return self.load_plugin(filepath, prev_module=previous_module, write_manifest=False)
        finally:
            self._write_web_route_manifest()

    def reload_plugin(self, plugin_id: str, cascade: bool = True) -> bool:
        """Reload a plugin, and by default reload loaded dependents as a chain."""
        result = self.reload_plugin_cascade(plugin_id) if cascade else {"success": self._reload_plugin_single(plugin_id)}
        return bool(result.get("success"))

    def reload_plugin_cascade(self, plugin_id: str) -> dict:
        """Reload a plugin and all plugins that load after it."""
        if plugin_id not in self.loaded_plugins:
            logger.error(f"Cannot reload '{plugin_id}': plugin is not loaded.")
            return {"success": False, "reloaded": [], "error": "Plugin is not loaded"}

        chain = self._get_loaded_suffix_chain(plugin_id)
        filepaths = {pid: self.plugin_file_map.get(pid) for pid in chain}
        previous_modules = {pid: self.loaded_plugins.get(pid) for pid in chain}
        missing = [pid for pid, path in filepaths.items() if not path]
        if missing:
            message = f"Missing source file location for plugins: {missing}"
            logger.error(message)
            return {"success": False, "reloaded": [], "error": message}

        logger.info(f"Reloading plugin chain for '{plugin_id}': {chain}")
        for pid in reversed(chain):
            if not self.unload_plugin(pid, write_manifest=False):
                self._write_web_route_manifest()
                return {"success": False, "reloaded": [], "error": f"Failed to unload {pid}"}

        reloaded = []
        for pid in chain:
            try:
                loaded = self.load_plugin(filepaths[pid], prev_module=previous_modules.get(pid), write_manifest=False)
            except Exception as e:
                self._write_web_route_manifest()
                return {"success": False, "reloaded": reloaded, "error": f"Failed to load {pid}: {e}"}
            if not loaded:
                self._write_web_route_manifest()
                return {"success": False, "reloaded": reloaded, "error": f"Failed to load {pid}"}
            reloaded.append(pid)

        self._write_web_route_manifest()
        return {"success": True, "reloaded": reloaded}

    def unload_plugin_cascade(self, plugin_id: str) -> dict:
        """Unload a plugin and all plugins that load after it."""
        if plugin_id not in self.loaded_plugins:
            logger.error(f"Cannot unload '{plugin_id}': plugin is not loaded.")
            return {"success": False, "unloaded": [], "error": "Plugin is not loaded"}

        chain = self._get_loaded_suffix_chain(plugin_id)
        logger.info(f"Unloading plugin chain for '{plugin_id}': {chain}")
        unloaded = []
        for pid in reversed(chain):
            if not self.unload_plugin(pid, write_manifest=False):
                self._write_web_route_manifest()
                return {"success": False, "unloaded": unloaded, "error": f"Failed to unload {pid}"}
            unloaded.append(pid)

        self._write_web_route_manifest()
        return {"success": True, "unloaded": unloaded}
