from flask import Blueprint, jsonify, request
from conductor.core.auth import current_user, error
from conductor.core.permission import PermissionLevel
from .service import BackupService
import os

prime_backup_bp = Blueprint('prime_backup', __name__)
_service: BackupService = None
_kernel_ref = None

@prime_backup_bp.before_request
def require_backup_user():
    user = current_user(_kernel_ref) if _kernel_ref else None
    if not user:
        return error("Unauthorized", 401)
    if request.method != "GET" and int(user.get("permission_level", 0)) < int(PermissionLevel.ADMIN):
        return error("Admin permission required", 403)

def init_service(db_url: str, storage_root: str, kernel):
    global _service, _kernel_ref
    _service = BackupService(db_url, storage_root)
    _kernel_ref = kernel

@prime_backup_bp.route('/status', methods=['GET'])
def api_status():
    return jsonify({
        "success": True,
        "data": {
            "enabled": True,
            "storage_root": str(_service.backup_engine.storage_root),
            "source_root": _kernel_ref.storage_dir if _kernel_ref else "./storage",
            "concurrency": 1
        }
    })

@prime_backup_bp.route('/list', methods=['GET'])
def api_list_backups():
    backups = _service.get_history()
    data = []
    for b in backups:
        data.append({
            "id": b.id,
            "creator": b.creator,
            "comment": b.comment,
            "timestamp": b.timestamp.timestamp(),
            "file_count": b.file_count,
            "total_raw_size": b.total_raw_size,
        })
    return jsonify({"success": True, "data": {"backups": data}})

@prime_backup_bp.route('/make', methods=['POST'])
def api_make_backup():
    req_data = request.json or {}
    comment = req_data.get("comment", "Manual backup from Web UI")
    creator = req_data.get("creator", "WebAdmin")
    
    from . import _config
    source_dir = _config.source_root
    
    try:
        # Runs synchronously for now, but should be backgrounded
        # since we are in a blueprint, we can use a thread
        import threading
        def run_backup():
            _service.create_backup(source_dir, creator, comment)
            
        threading.Thread(target=run_backup, daemon=True).start()
        return jsonify({"success": True, "message": "Backup task queued."})
    except Exception as e:
        return jsonify({"success": False, "errorMessage": str(e)})

@prime_backup_bp.route('/delete', methods=['POST'])
def api_delete_backup():
    req_data = request.json or {}
    backup_id = req_data.get("id")
    if not backup_id:
        return jsonify({"success": False, "errorMessage": "Missing backup id"})
        
    try:
        _service.delete_backup(backup_id)
        return jsonify({"success": True, "message": f"Backup #{backup_id} deleted."})
    except Exception as e:
        return jsonify({"success": False, "errorMessage": str(e)})

@prime_backup_bp.route('/restore', methods=['POST'])
def api_restore_backup():
    req_data = request.json or {}
    backup_id = req_data.get("id")
    target_path = req_data.get("path")
    if not all([backup_id, target_path]):
        return jsonify({"success": False, "errorMessage": "Missing id or path"})
        
    try:
        import threading
        def run_restore():
            _service.restore_backup(backup_id, target_path)
            
        threading.Thread(target=run_restore, daemon=True).start()
        return jsonify({"success": True, "message": "Restoration task queued."})
    except Exception as e:
        return jsonify({"success": False, "errorMessage": str(e)})
