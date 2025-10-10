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


@bp.route("/pair/<path:pair_identifiers>", methods=["GET"])
def get_registry_pair(pair_identifiers: str):
    """
    Retrieve registry information for a gene/strain pair.
    ---
    tags:
      - Registry
    parameters:
      - in: path
        name: pair_identifiers
        required: true
        schema:
          type: string
        description: Comma-separated identifiers, e.g. thrL,GCF_000005845.2.
    responses:
      200:
        description: Pair interop payload.
        content:
          application/json:
            schema:
              type: object
      400:
        description: Invalid pair identifier supplied.
      500:
        description: Unexpected server error.
    """
    try:
        gene_id, strain_id = [segment.strip() for segment in pair_identifiers.split(",", 1)]
    except ValueError:
        return jsonify({"error": "Pair identifier must include both gene and strain separated by a comma"}), 400

    if not gene_id or not strain_id:
        return jsonify({"error": "Gene and strain identifiers must both be provided"}), 400

    service = RegistryService(db)
    result = service.get_pair(gene_id=gene_id, strain_id=strain_id)
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
    entity_counts_result = db.session.execute(
        select(Entity.name, db.func.count(Mapping.uid))
        .join(Mapping, Mapping.entity_type_id == Entity.id)
        .group_by(Entity.name)
    ).all()
    entity_counts = {name.lower(): count for name, count in entity_counts_result}
    gene_count = entity_counts.get("gene", 0)
    strain_count = entity_counts.get("strain", 0)
    stmt = (
        select(
            Mapping,
            SourceDb.db_name.label("source_db_name"),
            Entity.name.label("entity_type_name"),
        )
        .join(SourceDb, Mapping.source_db_id == SourceDb.id)
        .join(Entity, Mapping.entity_type_id == Entity.id)
        .order_by(Mapping.updated_at.desc())
        .limit(1000)
    )

    if search_query:
        like_value = f"%{search_query}%"
        stmt = stmt.where(or_(Mapping.uid.ilike(like_value), Mapping.local_id.ilike(like_value)))

    result = db.session.execute(stmt).all()
    result_entity_counts = {"gene": 0, "strain": 0}
    for mapping, source_db_name, entity_type_name in result:
        entity_key = entity_type_name.lower()
        if entity_key in result_entity_counts:
            result_entity_counts[entity_key] += 1

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
        result_cap=1000,
        total_count=total_count,
        gene_count=gene_count,
        strain_count=strain_count,
        result_gene_count=result_entity_counts["gene"],
        result_strain_count=result_entity_counts["strain"],
    )
