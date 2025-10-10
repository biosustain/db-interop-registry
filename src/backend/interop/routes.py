from flask import jsonify, render_template, request
from sqlalchemy import or_, select

from backend import db
from backend.interop import bp
from backend.interop.enums import ResourceType
from backend.interop.models import Entity, Mapping, SourceDb
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
    parameters:
      - in: query
        name: q
        schema:
          type: string
        required: false
        description: Search term applied to UID or local ID.
    responses:
      200:
        description: HTML page containing registry mappings.
        content:
          text/html:
            schema:
              type: string
    """
    search_query = request.args.get("q", "").strip()
    total_count = db.session.execute(select(db.func.count()).select_from(Mapping)).scalar_one()
    stmt = (
        select(
            Mapping,
            SourceDb.db_name.label("source_db_name"),
            Entity.name.label("entity_type_name"),
        )
        .join(SourceDb, Mapping.source_db_id == SourceDb.id)
        .join(Entity, Mapping.entity_type_id == Entity.id)
        .order_by(Mapping.updated_at.desc())
        .limit(100)
    )

    if search_query:
        like_value = f"%{search_query}%"
        stmt = stmt.where(or_(Mapping.uid.ilike(like_value), Mapping.local_id.ilike(like_value)))

    result = db.session.execute(stmt).all()
    mappings = [
        {
            "mapping": mapping,
            "source_db_name": source_db_name,
            "entity_type_name": entity_type_name,
        }
        for mapping, source_db_name, entity_type_name in result
    ]
    return render_template(
        "mappings_list.html",
        mappings=mappings,
        search_query=search_query,
        result_cap=100,
        total_count=total_count,
    )
