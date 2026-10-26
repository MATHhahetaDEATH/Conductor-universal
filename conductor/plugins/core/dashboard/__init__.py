import time
import os
from flask import Blueprint, jsonify
from conductor.core.permission import PermissionLevel
from conductor.core.command.builder import SimpleCommandBuilder

PLUGIN_METADATA = {
    "id": "dashboard",
    "version": "1.0.0",
    "name": "System Dashboard",
    "description": "Kernel status and system overview.",
    "priority": 1100,
    "web_name": "Dashboard",
    "web_icon": "dashboard"
}

START_TIME = time.time()
_kernel_ref = None

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/status', methods=['GET'])
def get_status():
    uptime = time.time() - START_TIME
    return jsonify({
        "success": True,
        "data": {
            "version": PLUGIN_METADATA["version"],
            "uptime": int(uptime),
            "plugins_count": len(_kernel_ref.plugins.loaded_plugins),
            "debug": getattr(_kernel_ref, "debug", False),
            "pid": os.getpid()
        }
    })

def cmd_stop(source, ctx):
    source.reply("Shutting down Conductor...")
    _kernel_ref.stop()

def cmd_status(source, ctx):
    uptime = time.time() - START_TIME
    lines = [
        "--- Conductor Status ---",
        f"Uptime: {int(uptime // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s",
        f"Plugins: {len(_kernel_ref.plugins.loaded_plugins)}"
    ]
    source.reply("\n".join(lines))

def cmd_help(source, ctx):
    lines = ["--- Available Commands ---"]
    for cmd in _kernel_ref.get_all_commands():
        lines.append(f"{cmd['trigger']} - {cmd['description']} ({PermissionLevel(cmd['permission']).name})")
    source.reply("\n".join(lines))

def on_load(kernel, prev_module):
    global _kernel_ref
    _kernel_ref = kernel
    kernel.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    
    builder = SimpleCommandBuilder()
    builder.command("!!stop", cmd_stop, PermissionLevel.ADMIN, "Shut down kernel", "dashboard")
    builder.command("!!conductor stop", cmd_stop, PermissionLevel.ADMIN, "Shut down kernel", "dashboard")
    builder.command("!!status", cmd_status, PermissionLevel.USER, "Show kernel status", "dashboard")
    builder.command("!!conductor status", cmd_status, PermissionLevel.USER, "Show kernel status", "dashboard")
    builder.command("!!help", cmd_help, PermissionLevel.GUEST, "Show this help message", "dashboard")
    builder.command("!!conductor help", cmd_help, PermissionLevel.GUEST, "Show this help message", "dashboard")
    builder.register(kernel)
    kernel.logger.info("Dashboard plugin loaded.")
