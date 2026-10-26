import os
import sys
import threading
import time
import logging

from conductor.interface.api.app import create_app
from conductor.core.kernel import Kernel
from conductor.core.permission import CommandSource, PermissionLevel
from conductor.interface.console import cli_loop

class DynamicStdoutHandler(logging.StreamHandler):
    """Write to the active stdout so prompt_toolkit can patch it while prompting."""

    def emit(self, record):
        self.stream = sys.stdout
        super().emit(record)

def start_api(app, host, port, debug):
    """Run the Flask app in a background thread."""
    # Silence werkzeug logging to prevent prompt misalignment
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)
    app.run(host=host, port=port, debug=debug, use_reloader=False)

def main():
    debug = os.environ.get("CONDUCTOR_DEBUG", os.environ.get("FLASK_DEBUG", "")).lower() in {"1", "true", "yes", "on"}

    # Define plugin directories relative to this file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_dirs = [
        os.path.join(base_dir, "plugins", "core"),
        os.path.join(base_dir, "plugins")
    ]

    # Initialize kernel with storage inside the package directory
    storage_dir = os.path.join(base_dir, "storage")
    kernel = Kernel(plugin_dirs, storage_dir=storage_dir, debug=debug)
    console_handler = DynamicStdoutHandler()
    console_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s/%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logging.getLogger().addHandler(console_handler)
    
    # Start Kernel
    kernel.start()

    # Create Flask App
    app = create_app(kernel)
    port = int(os.environ.get("FLASK_RUN_PORT", 5678))
    host = os.environ.get("FLASK_RUN_HOST", "127.0.0.1")

    # Start Flask in a background daemon thread
    api_thread = threading.Thread(
        target=start_api, 
        args=(app, host, port, debug), 
        daemon=True
    )
    api_thread.start()

    # Run CLI in the main thread (blocking)
    try:
        cli_loop(kernel)
    finally:
        kernel.stop()
        # Small grace period for logs
        time.sleep(0.1)

if __name__ == "__main__":
    sys.exit(main())
