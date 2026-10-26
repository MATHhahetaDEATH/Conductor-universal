import os
import json
from flask import Blueprint, jsonify, request
from conductor.core.permission import PermissionLevel
from conductor.core.auth import current_user, error

PLUGIN_METADATA = {
    "id": "hello_world",
    "version": "1.0.0",
    "name": "Hello World Example Plugin",
    "description": "A minimal plugin to demonstrate standardized storage.",
    "author": "kasumitang",
    "web_name": "Hello World",
}

# Module-level variable to store kernel reference
_kernel = None
hello_world_bp = Blueprint("hello_world", __name__)

@hello_world_bp.before_request
def require_hello_user():
    if _kernel is None or not current_user(_kernel):
        return error("Unauthorized", 401)

def get_config():
    """Load greeting from config file."""
    config_dir = _kernel.get_plugin_config_dir("hello_world")
    config_path = os.path.join(config_dir, "config.json")
    default_config = {"greeting": "Hello"}
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            _kernel.logger.error(f"Failed to load config: {e}")
    
    # Save default if not exists
    with open(config_path, "w") as f:
        json.dump(default_config, f, indent=4)
    return default_config

def get_last_name():
    """Load last used name from data file."""
    data_dir = _kernel.get_plugin_data_dir("hello_world")
    state_path = os.path.join(data_dir, "state.json")
    if os.path.exists(state_path):
        try:
            with open(state_path, "r") as f:
                return json.load(f).get("last_name")
        except Exception:
            pass
    return "world"

def save_last_name(name):
    """Save the last used name to data file."""
    data_dir = _kernel.get_plugin_data_dir("hello_world")
    state_path = os.path.join(data_dir, "state.json")
    try:
        with open(state_path, "w") as f:
            json.dump({"last_name": name}, f, indent=4)
    except Exception as e:
        _kernel.logger.error(f"Failed to save state: {e}")

@hello_world_bp.route("/state", methods=["GET", "POST"])
def api_state():
    """Expose the same stored name used by the CLI command to web pages."""
    if request.method == "GET":
        return jsonify({
            "success": True,
            "data": {
                "greeting": get_config().get("greeting", "Hello"),
                "last_name": get_last_name(),
            },
        })

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip() or "world"
    save_last_name(name)
    return jsonify({
        "success": True,
        "data": {
            "greeting": get_config().get("greeting", "Hello"),
            "last_name": name,
        },
    })

def on_content(kernel, content_data):
    """Callback for the 'conductor.content_received' event."""
    kernel.logger.info(f"HelloWorld Plugin saw new content! ID: {content_data.id}, Source: {content_data.source}")

def sample_command(source, context):
    """Callback for the '!!hello' command."""
    # 1. Get greeting from config
    config = get_config()
    greeting = config.get("greeting", "Hello")
    
    # 2. Get name from context or data
    name = context.get('name')
    if not name:
        name = get_last_name()
    else:
        # Save new name to data
        save_last_name(name)
        
    source.reply(f"{greeting}, {name}! This is the Conductor Kernel responding.")

def on_load(kernel, prev_module):
    """Entry point for the plugin."""
    global _kernel
    _kernel = kernel
    
    # Use dedicated logger for per-plugin log files
    logger = kernel.get_logger("hello_world")
    logger.info("Initializing Hello World Plugin with Storage support...")
    
    # Register an event listener
    kernel.register_event_listener("conductor.content_received", on_content)
    kernel.register_blueprint(hello_world_bp, url_prefix="/api/hello_world")
    
    # Register commands
    kernel.register_command("!!hello <name>", sample_command, PermissionLevel.USER, "Say hello with context", "hello_world")
    kernel.register_command("!!hello", sample_command, PermissionLevel.USER, "Say hello using stored name", "hello_world")

    # Initialize config
    get_config()
