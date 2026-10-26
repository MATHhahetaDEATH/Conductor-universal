from __future__ import annotations

from flask import Flask

from .management import core_management_bp, register_management
from .web_cli import core_cli_bp, register_web_cli


def register_core_api(app: Flask, kernel) -> None:
    register_management(kernel)
    register_web_cli(kernel)
    app.register_blueprint(core_management_bp, url_prefix="/api/core")
    app.register_blueprint(core_cli_bp, url_prefix="/api/core/cli")
