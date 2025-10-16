import os

from flasgger import Swagger
from flask import Flask, jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.orm import DeclarativeBase


class BaseModel(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=BaseModel)
migrate = Migrate()
csrf = CSRFProtect()
SWAGGER_CONFIG = {
    "openapi": "3.0.2",
    "specs": [
        {
            "endpoint": "apispec_1",
            "route": "/api/openapi.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/apidocs_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "headers": [],
}

SWAGGER_TEMPLATE = {
    "info": {
        "title": "Interop Registry API",
        "description": "API documentation for Interop Registry services.",
        "version": "1.0.0",
    },
    "tags": [{"name": "Registry", "description": "Registry operations"}],
}


def create_app(config=None):
    app = Flask(__name__)

    # If RUNNING_IN_PRODUCTION is defined, then we're running on Azure
    if "RUNNING_IN_PRODUCTION" not in os.environ:
        print("Loading settings.development and environment variables from .env")
        app.config.from_object("backend.settings.development")
    else:  # pragma: no cover
        print("Loading settings.production")
        app.config.from_object("backend.settings.production")
    app.config.update(
        SQLALCHEMY_DATABASE_URI=app.config.get("DATABASE_URI"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    register_error_handlers(app)

    from backend.interop import bp as interop_bp

    app.register_blueprint(interop_bp)
    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)

    return app


def register_error_handlers(app):
    """Register custom error handlers for the application."""
    from backend.interop.utils.exceptions import (
        DatabaseInconsistencyError,
        InvalidResourceTypeError,
        ResourceNotFoundError,
    )

    def handle_resource_not_found(e):
        return jsonify({"detail": e.detail}), e.status_code

    def handle_invalid_resource_type(e):
        return jsonify({"detail": e.detail}), e.status_code

    def handle_database_inconsistency(e):
        return jsonify({"detail": e.detail}), e.status_code

    # Register them explicitly
    app.register_error_handler(ResourceNotFoundError, handle_resource_not_found)
    app.register_error_handler(InvalidResourceTypeError, handle_invalid_resource_type)
    app.register_error_handler(DatabaseInconsistencyError, handle_database_inconsistency)
