from flask import jsonify, render_template
from sqlalchemy import select

from backend import db
from backend.interop import bp
from backend.interop.enums import ResourceType
from backend.interop.models import Mapping
from backend.interop.services.registry import RegistryService


@bp.route("/<resource>/<string:local_id_or_uid>", methods=["GET"])
def get_registry_item(resource, local_id_or_uid):
    """
    Retrieve a registry item by resource type and identifier.
    ---
    tags:
      - Registry
    parameters:
      - in: path
        name: resource
        required: true
        schema:
          type: string
          enum: ["gene", "strain"]
        description: Type of resource to fetch.
      - in: path
        name: local_id_or_uid
        required: true
        schema:
          type: string
        description: Local identifier or UID of the resource.
    responses:
      200:
        description: Registry item located.
        content:
          application/json:
            schema:
              type: object
              additionalProperties: true
      400:
        description: Invalid resource type supplied.
        content:
          application/json:
            schema:
              type: object
              properties:
                error:
                  type: string
      404:
        description: Registry item not found.
      500:
        description: Unexpected server error.
    """
    # Validate resource type
    try:
        resource_type = ResourceType(resource)
    except ValueError:
        return jsonify({"error": f"Invalid resource type: {resource}. Must be 'gene' or 'strain'"}), 400

    service = RegistryService(db)
    result = service.get_registry_item(resource=resource_type.value, local_id_or_uid=local_id_or_uid)

    return jsonify(result), 200


@bp.route("/", methods=["GET"])
def index():
    """
    Render the HTML view of available mappings.
    ---
    tags:
      - Registry
    responses:
      200:
        description: HTML page containing registry mappings.
        content:
          text/html:
            schema:
              type: string
    """
    mappings = db.session.execute(select(Mapping)).scalars().all()
    return render_template("mappings_list.html", mappings=mappings)
