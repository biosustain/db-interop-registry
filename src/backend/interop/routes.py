import json
from datetime import UTC
from pathlib import Path

from flasgger import swag_from
from flask import jsonify, render_template, request
from sqlalchemy import or_, select

from backend import db
from backend.interop import bp
from backend.interop.enums import ResourceType
from backend.interop.models import Entity, Mapping, SourceDb, Synonym
from backend.interop.services.registry import RegistryService

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"
REGISTRY_ITEM_SCHEMA = json.loads((SCHEMAS_DIR / "registry_item_response.json").read_text())
REGISTRY_PAIR_SCHEMA = json.loads((SCHEMAS_DIR / "registry_pair_response.json").read_text())


@bp.route("/<resource>/<string:local_id_or_uid>", methods=["GET"])
@swag_from(
    {
        "tags": ["Registry"],
        "parameters": [
            {
                "in": "path",
                "name": "resource",
                "required": True,
                "schema": {"type": "string", "enum": ["gene", "strain"]},
                "description": "Type of resource to fetch.",
            },
            {
                "in": "path",
                "name": "local_id_or_uid",
                "required": True,
                "schema": {"type": "string"},
                "description": "Local identifier or UID of the resource.",
            },
        ],
        "responses": {
            200: {
                "description": "Registry item located.",
                "content": {
                    "application/json": {
                        "schema": REGISTRY_ITEM_SCHEMA
                    }
                },
            },
            400: {
                "description": "Invalid resource type supplied.",
                "content": {
                    "application/json": {
                        "schema": {"type": "object", "properties": {"error": {"type": "string"}}}
                    }
                },
            },
            404: {"description": "Registry item not found."},
            500: {"description": "Unexpected server error."},
        },
    }
)
def get_registry_item(resource, local_id_or_uid):
    """Retrieve a registry item by resource type and identifier."""
    # Validate resource type
    try:
        resource_type = ResourceType(resource)
    except ValueError:
        return jsonify({"error": f"Invalid resource type: {resource}. Must be 'gene' or 'strain'"}), 400

    service = RegistryService(db)
    result = service.get_registry_item(resource=resource_type.value, local_id_or_uid=local_id_or_uid)

    return jsonify(result), 200


@bp.route("/pair/<path:pair_identifiers>", methods=["GET"])
@swag_from(
    {
        "tags": ["Registry"],
        "parameters": [
            {
                "in": "path",
                "name": "pair_identifiers",
                "required": True,
                "schema": {"type": "string"},
                "description": "Comma-separated identifiers, e.g. thrL,GCF_000005845.2.",
            }
        ],
        "responses": {
            200: {
                "description": "Pair interop payload.",
                "content": {
                    "application/json": {
                        "schema": REGISTRY_PAIR_SCHEMA
                    }
                },
            },
            400: {"description": "Invalid pair identifier supplied."},
            500: {"description": "Unexpected server error."},
        },
    }
)
def get_registry_pair(pair_identifiers: str):
    """Retrieve registry information for a gene/strain pair."""
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
@swag_from(
    {
        "tags": ["Registry"],
        "parameters": [
            {
                "in": "query",
                "name": "q",
                "schema": {"type": "string"},
                "required": False,
                "description": "Search term applied to UID or local ID.",
            }
        ],
        "responses": {
            200: {
                "description": "HTML page containing registry mappings.",
                "content": {"text/html": {"schema": {"type": "string"}}},
            }
        },
    }
)
def index():
    """Render the HTML view of available mappings."""
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

    def _format_updated_at(dt):
        if dt is None:
            return "Unknown"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).strftime("%b %d, %Y %H:%M UTC")

    result_entity_counts = {"gene": 0, "strain": 0}
    for mapping, source_db_name, entity_type_name in result:
        entity_key = entity_type_name.lower()
        if entity_key in result_entity_counts:
            result_entity_counts[entity_key] += 1

    uid_to_local_ids: dict[str, set[str]] = {}
    for mapping, _, _ in result:
        if mapping.uid:
            uid_to_local_ids.setdefault(mapping.uid, set()).add(mapping.local_id)

    uid_list = list(uid_to_local_ids.keys())
    local_id_list = [mapping.local_id for mapping, _, _ in result]

    synonyms_by_uid: dict[str, set[str]] = {uid: set() for uid in uid_list}
    synonym_to_parent_uids: dict[str, set[str]] = {}

    filters = []
    if uid_list:
        filters.append(Synonym.uid.in_(uid_list))
    if local_id_list:
        filters.append(Synonym.synonym.in_(local_id_list))

    synonym_rows = []
    if filters:
        synonym_rows = db.session.execute(select(Synonym.uid, Synonym.synonym).where(or_(*filters))).all()

    parent_uids = set()
    for uid, synonym in synonym_rows:
        if not synonym:
            continue
        synonyms_by_uid.setdefault(uid, set()).add(synonym)
        synonym_to_parent_uids.setdefault(synonym, set()).add(uid)
        parent_uids.add(uid)

    missing_parent_uids = parent_uids - uid_to_local_ids.keys()
    if missing_parent_uids:
        parent_mappings = db.session.execute(
            select(Mapping.uid, Mapping.local_id).where(Mapping.uid.in_(missing_parent_uids))
        ).all()
        for uid, local_id in parent_mappings:
            uid_to_local_ids.setdefault(uid, set()).add(local_id)

    mappings = [
        {
            "mapping": mapping,
            "source_db_name": source_db_name,
            "entity_type_name": entity_type_name,
            "updated_at_display": _format_updated_at(mapping.updated_at),
            "synonyms": sorted(
                {
                    *synonyms_by_uid.get(mapping.uid, set()),
                    *uid_to_local_ids.get(mapping.uid, set()),
                    *(
                        {
                            alt
                            for parent_uid in synonym_to_parent_uids.get(mapping.local_id, set())
                            for alt in (
                                uid_to_local_ids.get(parent_uid, set())
                                | synonyms_by_uid.get(parent_uid, set())
                            )
                        }
                    ),
                }
                - {mapping.local_id}
            ),
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
