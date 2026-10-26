import json
from pathlib import Path

class Config:
    def __init__(self, path: Path):
        self.path = path
        # Default keys following original PrimeBackup structure
        self.data = {
            "enabled": True,
            "debug": False,
            "storage_root": "./backup",
            "backup": {
                "source_root": "./storage",
                "targets": ["*"],
                "ignore_patterns": ["**/session.lock", "**/backup/**"]
            }
        }
        self.load()

    def load(self):
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        else:
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    @property
    def enabled(self) -> bool:
        return self.data.get("enabled", True)
    
    @property
    def storage_root(self) -> str:
        # User ensures it's relative or absolute
        return self.data.get("storage_root", "./backup")
    
    @property
    def source_root(self) -> str:
        backup_cfg = self.data.get("backup", {})
        return backup_cfg.get("source_root", "./storage")

    @property
    def targets(self) -> list:
        backup_cfg = self.data.get("backup", {})
        return backup_cfg.get("targets", ["*"])

    @property
    def ignore_patterns(self) -> list:
        backup_cfg = self.data.get("backup", {})
        return backup_cfg.get("ignore_patterns", [])
