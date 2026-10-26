from __future__ import annotations

import argparse
import os
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from conductor.core.dependencies import DependencyManager


def plugin_roots() -> list[str]:
    return [
        os.path.join(PROJECT_ROOT, "conductor", "plugins", "core"),
        os.path.join(PROJECT_ROOT, "conductor", "plugins"),
    ]


def iter_plugin_paths() -> list[tuple[str, str]]:
    plugin_roots_list = plugin_roots()
    plugins: list[tuple[str, str]] = []
    for root in plugin_roots_list:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.startswith("__"):
                continue
            path = os.path.join(root, name)
            if os.path.isdir(path) and os.path.exists(os.path.join(path, "__init__.py")):
                plugins.append((name, path))
    return plugins


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Conductor plugin dependencies into project manifests.")
    parser.add_argument("--ecosystem", choices=["all", "python", "web"], default="all")
    parser.add_argument("--install", action="store_true", help="Run poetry install/yarn install after syncing.")
    args = parser.parse_args()

    manager = DependencyManager(os.path.join(PROJECT_ROOT, "WebApp"), plugin_roots())
    for plugin_id, path in iter_plugin_paths():
        manager.update_plugin(plugin_id, path)

    result = manager.ensure_project_dependencies(args.ecosystem, install=args.install)
    for change in result["sync"].get("changes", []):
        added = ", ".join(item["name"] for item in change.get("added", [])) or "none"
        print(f"[{change['ecosystem']}] {change['path']} added: {added}")
    for command in result.get("commands", []):
        print(f"[{command['ecosystem']}] {' '.join(command['command'])} -> {command['returncode']}")
        if command.get("stderr"):
            print(command["stderr"].strip())
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
