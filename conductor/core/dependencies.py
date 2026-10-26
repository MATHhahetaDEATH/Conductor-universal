from __future__ import annotations

import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import ast
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

try:
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
except Exception:  # pragma: no cover - packaging is expected with Poetry/pip.
    Requirement = None
    SpecifierSet = None


@dataclass
class DependencyDecl:
    plugin_id: str
    ecosystem: str
    name: str
    spec: str
    source: str


@dataclass
class PluginRecord:
    plugin_id: str
    path: str
    entry: str
    is_core: bool
    metadata: Dict[str, Any]


class DependencyManager:
    """Track plugin Python/Web dependencies and sync them into project manifests."""

    def __init__(self, webapp_base: str, plugin_dirs: List[str]) -> None:
        self.webapp_base = webapp_base
        self.plugin_dirs = plugin_dirs
        self.project_base = os.path.abspath(os.path.join(webapp_base, ".."))
        self._decls_by_plugin: Dict[str, List[DependencyDecl]] = {}
        self._plugin_records: Dict[str, PluginRecord] = {}

    def update_plugin(self, plugin_id: str, plugin_path: str) -> None:
        self._decls_by_plugin[plugin_id] = self._read_plugin_deps(plugin_id, plugin_path)
        record = self._build_plugin_record(plugin_path, self._infer_is_core(plugin_path))
        if record and record.plugin_id == plugin_id:
            self._plugin_records[plugin_id] = record

    def remove_plugin(self, plugin_id: str) -> None:
        record = self._plugin_records.get(plugin_id)
        if record and os.path.exists(record.path):
            return
        self._decls_by_plugin.pop(plugin_id, None)
        self._plugin_records.pop(plugin_id, None)

    def scan_plugin_dirs(self) -> Dict[str, PluginRecord]:
        records: Dict[str, PluginRecord] = {}
        decls: Dict[str, List[DependencyDecl]] = {}

        for pdir in self.plugin_dirs:
            if not os.path.isdir(pdir):
                continue
            is_core_dir = self._infer_is_core(pdir)
            for item in sorted(os.listdir(pdir)):
                if item.startswith("__"):
                    continue
                item_path = os.path.join(pdir, item)
                if not self._is_plugin_candidate(item_path):
                    continue
                record = self._build_plugin_record(item_path, is_core_dir)
                if not record:
                    continue
                records[record.plugin_id] = record
                decls[record.plugin_id] = self._read_plugin_deps(record.plugin_id, record.path)

        self._plugin_records = dict(sorted(records.items()))
        self._decls_by_plugin = {plugin_id: decls.get(plugin_id, []) for plugin_id in self._plugin_records}
        return self._plugin_records

    def get_plugin_records(self) -> Dict[str, Dict[str, Any]]:
        return {
            plugin_id: {
                "plugin_id": record.plugin_id,
                "path": record.path,
                "entry": record.entry,
                "is_core": record.is_core,
                "metadata": record.metadata,
            }
            for plugin_id, record in sorted(self._plugin_records.items())
        }

    def _read_plugin_deps(self, plugin_id: str, plugin_path: str) -> List[DependencyDecl]:
        if not os.path.isdir(plugin_path):
            return []

        deps: List[DependencyDecl] = []
        req_path = os.path.join(plugin_path, "requirements.txt")
        if os.path.exists(req_path):
            deps.extend(self._read_requirements(plugin_id, req_path))

        package_path = os.path.join(plugin_path, "web", "package.json")
        if os.path.exists(package_path):
            deps.extend(self._read_package_json(plugin_id, package_path))

        return deps

    def _is_plugin_candidate(self, path: str) -> bool:
        if path.endswith(".py") and os.path.isfile(path):
            return True
        return os.path.isdir(path) and os.path.isfile(os.path.join(path, "__init__.py"))

    def _infer_is_core(self, path: str) -> bool:
        return "core" in os.path.abspath(path).split(os.sep)

    def _plugin_entry(self, plugin_path: str) -> str:
        if os.path.isdir(plugin_path):
            return os.path.join(plugin_path, "__init__.py")
        return plugin_path

    def _build_plugin_record(self, plugin_path: str, is_core: bool) -> Optional[PluginRecord]:
        entry = self._plugin_entry(plugin_path)
        metadata = self._read_plugin_metadata(entry)
        if not metadata:
            return None
        plugin_id = str(metadata.get("id") or os.path.splitext(os.path.basename(entry))[0])
        return PluginRecord(
            plugin_id=plugin_id,
            path=plugin_path,
            entry=entry,
            is_core=is_core,
            metadata=metadata,
        )

    def _read_plugin_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            module = ast.parse(source, filename=path)
        except Exception:
            return None

        for node in module.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"PLUGIN_METADATA", "METADATA"}:
                    try:
                        value = ast.literal_eval(node.value)
                    except Exception:
                        return None
                    if isinstance(value, dict):
                        return value
        return None

    def _read_requirements(self, plugin_id: str, path: str) -> List[DependencyDecl]:
        deps = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith("#") or raw.startswith("-"):
                    continue
                name = raw
                spec = ""
                if Requirement:
                    try:
                        req = Requirement(raw)
                        name = req.name
                        spec = str(req.specifier)
                    except Exception:
                        name, spec = self._split_python_requirement(raw)
                else:
                    name, spec = self._split_python_requirement(raw)
                deps.append(DependencyDecl(plugin_id, "python", name, spec, path))
        return deps

    def _split_python_requirement(self, raw: str) -> tuple[str, str]:
        match = re.match(r"^([A-Za-z0-9_.-]+)(.*)$", raw)
        if not match:
            return raw, ""
        return match.group(1), match.group(2).strip()

    def _read_package_json(self, plugin_id: str, path: str) -> List[DependencyDecl]:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        deps = []
        for section in ("dependencies", "peerDependencies"):
            for name, spec in (payload.get(section) or {}).items():
                deps.append(DependencyDecl(plugin_id, "web", name, str(spec), path))
        return deps

    def get_status(self) -> Dict[str, Any]:
        self.scan_plugin_dirs()
        rows = []
        grouped: Dict[tuple[str, str], List[DependencyDecl]] = {}
        for decls in self._decls_by_plugin.values():
            for decl in decls:
                grouped.setdefault((decl.ecosystem, decl.name), []).append(decl)

        for (ecosystem, name), decls in sorted(grouped.items()):
            installed = self._installed_version(ecosystem, name)
            ok = self._matches(installed, [decl.spec for decl in decls], ecosystem)
            rows.append({
                "ecosystem": ecosystem,
                "name": name,
                "specs": sorted({decl.spec or "*" for decl in decls}),
                "installed": installed,
                "status": "ok" if ok else ("missing" if not installed else "version_mismatch"),
                "plugins": sorted({decl.plugin_id for decl in decls}),
                "source_files": sorted({decl.source for decl in decls}),
                "can_remove_if_plugins_removed": len({decl.plugin_id for decl in decls}) == 1,
            })

        return {
            "dependencies": rows,
            "plugins": {
                plugin_id: [decl.__dict__ for decl in decls]
                for plugin_id, decls in sorted(self._decls_by_plugin.items())
            },
            "plugin_records": self.get_plugin_records(),
            "next_actions": self._next_actions(rows),
            "manifest_sync": self.preview_manifest_sync(),
        }

    def preview_manifest_sync(self, ecosystem: str = "all") -> Dict[str, Any]:
        """Return project manifest changes that would be made for plugin dependencies."""
        if ecosystem not in {"all", "python", "web"}:
            raise ValueError("ecosystem must be one of: all, python, web")

        result = {
            "python": self._preview_python_manifest() if ecosystem in {"all", "python"} else {"add": [], "existing": []},
            "web": self._preview_web_manifest() if ecosystem in {"all", "web"} else {"add": [], "existing": []},
        }
        return result

    def sync_manifests(self, ecosystem: str = "all") -> Dict[str, Any]:
        """Register plugin dependencies into pyproject.toml and WebApp/package.json."""
        if ecosystem not in {"all", "python", "web"}:
            raise ValueError("ecosystem must be one of: all, python, web")

        changes = []
        if ecosystem in {"all", "python"}:
            changes.append(self._sync_python_manifest())
        if ecosystem in {"all", "web"}:
            changes.append(self._sync_web_manifest())

        return {
            "success": True,
            "changes": changes,
            "status": self.get_status(),
        }

    def ensure_project_dependencies(self, ecosystem: str = "all", install: bool = True) -> Dict[str, Any]:
        """Sync plugin dependencies into manifests and optionally run Poetry/Yarn install."""
        sync_result = self.sync_manifests(ecosystem)
        commands = []

        if install:
            status = sync_result["status"]
            missing_ecosystems = {
                row["ecosystem"]
                for row in status["dependencies"]
                if row["status"] != "ok" and (ecosystem == "all" or row["ecosystem"] == ecosystem)
            }
            if "python" in missing_ecosystems:
                poetry = shutil.which("poetry")
                if poetry:
                    commands.append(self._run_command([poetry, "install"], cwd=self.project_base, ecosystem="python"))
                else:
                    commands.append({
                        "ecosystem": "python",
                        "command": ["poetry", "install"],
                        "cwd": self.project_base,
                        "returncode": 127,
                        "stdout": "",
                        "stderr": "poetry executable not found",
                    })
            if "web" in missing_ecosystems:
                yarn = shutil.which("yarn")
                if yarn:
                    commands.append(self._run_command([yarn, "install"], cwd=self.webapp_base, ecosystem="web"))
                else:
                    commands.append({
                        "ecosystem": "web",
                        "command": ["yarn", "install"],
                        "cwd": self.webapp_base,
                        "returncode": 127,
                        "stdout": "",
                        "stderr": "yarn executable not found",
                    })

        return {
            "success": all(item["returncode"] == 0 for item in commands),
            "sync": sync_result,
            "commands": commands,
            "status": self.get_status(),
        }

    def install_missing(self, ecosystem: str = "all") -> Dict[str, Any]:
        """Install currently missing or mismatched plugin dependencies.

        Args:
            ecosystem: ``python``, ``web``, or ``all``.

        Returns:
            A structured result containing executed commands and refreshed status.
        """
        if ecosystem not in {"all", "python", "web"}:
            raise ValueError("ecosystem must be one of: all, python, web")

        status = self.get_status()
        rows = [
            row for row in status["dependencies"]
            if row["status"] != "ok" and (ecosystem == "all" or row["ecosystem"] == ecosystem)
        ]
        python_specs = self._specs_for(rows, "python")
        web_specs = self._specs_for(rows, "web")
        commands = []

        if python_specs:
            command = [sys.executable, "-m", "pip", "install", *python_specs]
            commands.append(self._run_command(command, cwd=None, ecosystem="python"))

        if web_specs:
            command = ["yarn", "add", *web_specs]
            commands.append(self._run_command(command, cwd=self.webapp_base, ecosystem="web"))

        return {
            "success": all(item["returncode"] == 0 for item in commands),
            "commands": commands,
            "status": self.get_status(),
        }

    def _all_decls(self, ecosystem: str) -> List[DependencyDecl]:
        return [
            decl
            for decls in self._decls_by_plugin.values()
            for decl in decls
            if decl.ecosystem == ecosystem
        ]

    def _plugin_specs(self, ecosystem: str) -> Dict[str, Dict[str, Any]]:
        specs: Dict[str, Dict[str, Any]] = {}
        for decl in self._all_decls(ecosystem):
            spec = decl.spec or "*"
            item = specs.setdefault(decl.name, {
                "name": decl.name,
                "spec": spec,
                "plugins": set(),
                "source_files": set(),
            })
            item["plugins"].add(decl.plugin_id)
            item["source_files"].add(decl.source)
        return dict(sorted(specs.items()))

    def _preview_python_manifest(self) -> Dict[str, Any]:
        pyproject_path = os.path.join(self.project_base, "pyproject.toml")
        existing = self._read_poetry_dependency_specs(pyproject_path)
        add = []
        present = []
        for name, item in self._plugin_specs("python").items():
            spec = item["spec"]
            if name in existing:
                present.append({
                    "name": name,
                    "required": spec,
                    "current": existing[name],
                    "plugins": sorted(item["plugins"]),
                    "source_files": sorted(item["source_files"]),
                })
            else:
                add.append({
                    "name": name,
                    "spec": spec,
                    "plugins": sorted(item["plugins"]),
                    "source_files": sorted(item["source_files"]),
                })
        return {"path": pyproject_path, "add": add, "existing": present}

    def _preview_web_manifest(self) -> Dict[str, Any]:
        package_path = os.path.join(self.webapp_base, "package.json")
        existing = self._read_package_dependency_specs(package_path)
        add = []
        present = []
        for name, item in self._plugin_specs("web").items():
            spec = item["spec"]
            if name in existing:
                present.append({
                    "name": name,
                    "required": spec,
                    "current": existing[name],
                    "plugins": sorted(item["plugins"]),
                    "source_files": sorted(item["source_files"]),
                })
            else:
                add.append({
                    "name": name,
                    "spec": spec,
                    "plugins": sorted(item["plugins"]),
                    "source_files": sorted(item["source_files"]),
                })
        return {"path": package_path, "add": add, "existing": present}

    def _sync_python_manifest(self) -> Dict[str, Any]:
        preview = self._preview_python_manifest()
        pyproject_path = preview["path"]
        additions = preview["add"]
        if not additions:
            return {"ecosystem": "python", "path": pyproject_path, "added": [], "existing": preview["existing"]}

        with open(pyproject_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines()
        section_start = None
        section_end = len(lines)
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "[tool.poetry.dependencies]":
                section_start = index
                continue
            if section_start is not None and index > section_start and stripped.startswith("[") and stripped.endswith("]"):
                section_end = index
                break

        if section_start is None:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append("[tool.poetry.dependencies]")
            section_start = len(lines) - 1
            section_end = len(lines)

        insertion = [f"{item['name']} = {json.dumps(item['spec'])}" for item in additions]
        if section_end < len(lines) and lines[section_end].strip().startswith("["):
            insertion.append("")
        lines[section_end:section_end] = insertion
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return {
            "ecosystem": "python",
            "path": pyproject_path,
            "added": additions,
            "existing": preview["existing"],
        }

    def _sync_web_manifest(self) -> Dict[str, Any]:
        preview = self._preview_web_manifest()
        package_path = preview["path"]
        additions = preview["add"]
        if not additions:
            return {"ecosystem": "web", "path": package_path, "added": [], "existing": preview["existing"]}

        with open(package_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        dependencies = payload.setdefault("dependencies", {})
        for item in additions:
            dependencies[item["name"]] = item["spec"]

        with open(package_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")

        return {
            "ecosystem": "web",
            "path": package_path,
            "added": additions,
            "existing": preview["existing"],
        }

    def _read_poetry_dependency_specs(self, pyproject_path: str) -> Dict[str, str]:
        if not os.path.exists(pyproject_path):
            return {}
        specs: Dict[str, str] = {}
        in_section = False
        with open(pyproject_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped == "[tool.poetry.dependencies]":
                    in_section = True
                    continue
                if in_section and stripped.startswith("[") and stripped.endswith("]"):
                    break
                if not in_section or not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                name, value = stripped.split("=", 1)
                name = name.strip().strip('"')
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                specs[name] = value
        return specs

    def _read_package_dependency_specs(self, package_path: str) -> Dict[str, str]:
        if not os.path.exists(package_path):
            return {}
        with open(package_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return {
            **(payload.get("dependencies") or {}),
            **(payload.get("devDependencies") or {}),
            **(payload.get("peerDependencies") or {}),
        }

    def _installed_version(self, ecosystem: str, name: str) -> Optional[str]:
        if ecosystem == "python":
            try:
                return importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                return None

        package_path = os.path.join(self.webapp_base, "node_modules", name, "package.json")
        if not os.path.exists(package_path):
            return None
        try:
            with open(package_path, "r", encoding="utf-8") as f:
                return json.load(f).get("version")
        except Exception:
            return None

    def _matches(self, installed: Optional[str], specs: Iterable[str], ecosystem: str) -> bool:
        if not installed:
            return False
        if ecosystem == "web":
            return True
        for spec in specs:
            if not spec or spec == "*":
                continue
            if SpecifierSet and installed not in SpecifierSet(spec):
                return False
        return True

    def _next_actions(self, rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        python_rows = [row for row in rows if row["ecosystem"] == "python" and row["status"] != "ok"]
        web_rows = [row for row in rows if row["ecosystem"] == "web" and row["status"] != "ok"]
        actions: Dict[str, Dict[str, Any]] = {}

        if python_rows:
            actions["python"] = {
                "manifest": os.path.join(self.project_base, "pyproject.toml"),
                "title": "Update root Poetry manifest",
                "button_label": "Update pyproject.toml",
                "sync_ecosystem": "python",
                "follow_up": [
                    "Stop the backend if it is running.",
                    "Run poetry install to refresh the virtualenv and lockfile.",
                    "Restart Conductor after Poetry finishes.",
                ],
                "dependencies": [
                    {"name": row["name"], "specs": row["specs"], "plugins": row["plugins"]}
                    for row in python_rows
                ],
            }

        if web_rows:
            actions["web"] = {
                "manifest": os.path.join(self.webapp_base, "package.json"),
                "title": "Update root Yarn manifest",
                "button_label": "Update WebApp/package.json",
                "sync_ecosystem": "web",
                "follow_up": [
                    "Stop the WebApp process if it is running.",
                    "Run yarn install in WebApp to refresh node_modules and yarn.lock.",
                    "Restart the WebApp process after Yarn finishes.",
                ],
                "dependencies": [
                    {"name": row["name"], "specs": row["specs"], "plugins": row["plugins"]}
                    for row in web_rows
                ],
            }

        return actions

    def _specs_for(self, rows: List[Dict[str, Any]], ecosystem: str) -> List[str]:
        specs = []
        for row in rows:
            if row["ecosystem"] != ecosystem:
                continue
            spec = row["specs"][0]
            if ecosystem == "python":
                specs.append(f"{row['name']}{'' if spec == '*' else spec}")
            else:
                specs.append(f"{row['name']}@{spec}" if spec != "*" else row["name"])
        return specs

    def _run_command(self, command: List[str], cwd: Optional[str], ecosystem: str) -> Dict[str, Any]:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return {
            "ecosystem": ecosystem,
            "command": command,
            "cwd": cwd,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-12000:],
        }
