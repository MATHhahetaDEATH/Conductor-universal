from flask import Flask

from .routes import register_routes
from conductor.core.kernel import Kernel
from conductor.core.system_api import register_core_api

def create_app(kernel: Kernel) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config['KERNEL'] = kernel
    
    # Register blueprints/routes
    register_routes(app, kernel)

    # Core management and terminal APIs are part of the kernel, not plugins.
    register_core_api(app, kernel)
    
    # Register dynamic plugin blueprints
    for bp, prefix in kernel._blueprints:
        app.register_blueprint(bp, url_prefix=prefix)
    
    return app
