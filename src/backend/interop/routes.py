from flask import redirect, render_template, request, url_for, jsonify
from sqlalchemy import select

from backend import db
from backend.interop import bp
from backend.interop.models import Mapping
from backend.interop.enums import ResourceType
from backend.interop.services.registry import RegistryService

@bp.route("/<resource>/<string:local_id_or_uid>", methods=["GET"])
def get_registry_item(resource, local_id_or_uid):
    # Validate resource type
    try:
        resource_type = ResourceType(resource)
    except ValueError:
        return jsonify({
            "error": f"Invalid resource type: {resource}. Must be 'gene' or 'strain'"
        }), 400
    
    service = RegistryService(db)
    result = service.get_registry_item(
        resource=resource_type.value,
        local_id_or_uid=local_id_or_uid
    )

    return jsonify(result), 200
    

@bp.route("/", methods=["GET"])
def index():
    mappings = db.session.execute(select(Mapping)).scalars().all()
    return render_template("mappings_list.html", mappings=mappings)