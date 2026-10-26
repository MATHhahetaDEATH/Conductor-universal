import os
import threading
from pathlib import Path
from conductor.core.kernel import Kernel
from conductor.core.permission import PermissionLevel
from .config import Config
from .prime_backup_bp import prime_backup_bp, init_service

PLUGIN_METADATA = {
    "id": "prime_backup",
    "version": "2.0.0-web",
    "name": "PrimeBackup (Native)",
    "description": "Native high-performance deduplicated backup system for Conductor.",
    "author": "kasumitang",
    "priority": 100,
    "web_name": "Prime Backup",
    "web_icon": "save"
}

_kernel: Kernel = None
_config: Config = None

def on_load(kernel: Kernel, old_module):
    global _kernel, _config
    _kernel = kernel
    
    # 1. Load config
    config_path = Path(kernel.get_plugin_config_dir("prime_backup")) / "config.json"
    _config = Config(config_path)
    
    # Calculate relative paths for backup (relative to CWD, which is Conductor Root)
    storage_root = _config.storage_root
    db_path = os.path.join(kernel.get_plugin_data_dir("prime_backup"), "prime_backup.db")
    db_url = f"sqlite:///{db_path}"
    
    # 2. Initialize Service and Blueprint
    init_service(db_url, storage_root, kernel)
    kernel.register_blueprint(prime_backup_bp, url_prefix='/api/prime_backup')
    
    # 3. Register Commands
    def cmd_make(source, ctx):
        comment = ctx.get("comment", "Manual backup")
        source.reply(f"Starting backup: {comment}...")
        
        def run():
            try:
                # Source is configured in config.json
                from .prime_backup_bp import _service
                source_dir = _config.source_root
                backup = _service.create_backup(source_dir, source.name, comment)
                source.reply(f"Backup completed! ID: {backup.id}, Files: {backup.file_count}, Size: {backup.total_raw_size / 1024 / 1024:.2f} MB")
            except Exception as e:
                source.reply(f"Backup failed: {str(e)}")
        
        threading.Thread(target=run, daemon=True).start()

    def cmd_list(source, ctx):
        from .prime_backup_bp import _service
        backups = _service.get_history()
        if not backups:
            source.reply("No backups found.")
            return
        
        lines = ["--- Backup History ---"]
        for b in backups[:10]: # Show last 10
            lines.append(f"#{b.id} [{b.timestamp.strftime('%Y-%m-%d %H:%M')}] {b.comment} (by {b.creator})")
        source.reply("\n".join(lines))

    def cmd_restore(source, ctx):
        backup_id = int(ctx.get("id"))
        target_path = ctx.get("path")
        source.reply(f"Starting restoration of backup #{backup_id} to {target_path}...")
        
        def run():
            try:
                from .prime_backup_bp import _service
                _service.restore_backup(backup_id, target_path)
                source.reply(f"Restoration of #{backup_id} completed successfully.")
            except Exception as e:
                source.reply(f"Restoration failed: {str(e)}")
        
        threading.Thread(target=run, daemon=True).start()

    def cmd_delete(source, ctx):
        backup_id = int(ctx.get("id"))
        source.reply(f"Deleting backup #{backup_id}...")
        try:
            from .prime_backup_bp import _service
            _service.delete_backup(backup_id)
            source.reply(f"Backup #{backup_id} deleted.")
        except Exception as e:
            source.reply(f"Deletion failed: {str(e)}")

    # Conductor Native registration
    kernel.register_command("!!pb make", cmd_make, PermissionLevel.ADMIN, "Create a backup", "prime_backup")
    kernel.register_command("!!pb make <comment>", cmd_make, PermissionLevel.ADMIN, "Create a backup with comment", "prime_backup")
    kernel.register_command("!!pb list", cmd_list, PermissionLevel.ADMIN, "List backups", "prime_backup")
    kernel.register_command("!!pb restore <id> <path>", cmd_restore, PermissionLevel.ADMIN, "Restore a backup to a path", "prime_backup")
    kernel.register_command("!!pb back <id> <path>", cmd_restore, PermissionLevel.ADMIN, "Alias for !!pb restore", "prime_backup")
    kernel.register_command("!!pb delete <id>", cmd_delete, PermissionLevel.ADMIN, "Delete a backup", "prime_backup")

    kernel.logger.info("PrimeBackup Native loaded successfully.")

def on_unload(kernel: Kernel):
    kernel.logger.info("PrimeBackup Native unloaded.")
