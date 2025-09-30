from flask import Blueprint

bp = Blueprint("interop", __name__)

from backend.interop import routes  # noqa

__all__ = [
    "routes",
]
