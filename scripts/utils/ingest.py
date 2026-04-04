"""Ingest utilities."""

import datetime
import hashlib
import json
import sys
import time
from pathlib import Path

from sqlalchemy import insert, tuple_, update
from utils.db_connector import commit_with_retry, get_session
from utils.models import AuditLog, Entity, Mapping, Registry, SourceDb, Synonym
from utils.ncbi_assemblies import fetch_ncbi_assemblies, fetch_ncbi_gene_synonyms
from utils.uniprot import fetch_uniprot_id

BATCH_SIZE = 5_000

def validate_entity_type(entity_type: str) -> str:
    """
    Validate and normalize entity type.

    Args:
        entity_type: The entity type to validate

    Returns:
        Normalized entity type

    Raises:
        ValueError: If entity type is not valid
    """
    normalized = entity_type.lower()
    if normalized not in ["gene", "strain"]:
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be 'gene' or 'strain'")
    return normalized


def generate_uid(entity_type: str, local_id: str) -> str:
    """
    Generate a unique identifier based on entity type and local_id.

    Args:
        entity_type: "gene" or "strain"
        local_id: The local identifier

    Returns:
        Unique ID with prefix (G- for genes, S- for strains)
    """
    # Create a deterministic hash from the local_id
    hash_input = f"{entity_type}:{local_id}".encode()
    hash_digest = hashlib.sha256(hash_input).hexdigest()[:12]

    # Add appropriate prefix
    prefix = "G-" if entity_type.lower() == "gene" else "S-"
    return f"{prefix}{hash_digest.upper()}"


def build_source_db_cache(db_session) -> dict[str, int]:
    """Return a mapping of source database names to their IDs."""
    return {row.db_name: row.id for row in db_session.query(SourceDb).all()}


def build_entity_type_cache(db_session) -> dict[str, int]:
    """Return a mapping of normalised entity type names to their IDs."""
    return {row.name.lower(): row.id for row in db_session.query(Entity).all()}


def get_source_db_id(db_session, db_name: str, cache: dict[str, int] | None = None) -> int:
    """
    Get the source_db_id for a given database name.

    Args:
        db_session: Database session
        db_name: Name of the source database

    Returns:
        The ID of the source database

    Raises:
        ValueError: If database name not found
    """
    if cache is not None and db_name in cache:
        return cache[db_name]

    source_db = db_session.query(SourceDb).filter(SourceDb.db_name == db_name).first()

    if not source_db:
        available_dbs = db_session.query(SourceDb.db_name).all()
        available_names = [db.db_name for db in available_dbs]
        raise ValueError(f"Source database '{db_name}' not found. Available databases: {available_names}")

    if cache is not None:
        cache[db_name] = source_db.id
    return source_db.id


def get_entity_type_id(db_session, entity_type: str, cache: dict[str, int] | None = None) -> int:
    """
    Get the entity_type_id for a given entity type.

    Args:
        db_session: Database session
        entity_type: "gene" or "strain"

    Returns:
        The ID of the entity type

    Raises:
        ValueError: If entity type not found
    """
    lookup_key = entity_type.lower()

    if cache is not None and lookup_key in cache:
        return cache[lookup_key]

    entity = db_session.query(Entity).filter(Entity.name.ilike(entity_type)).first()
    if not entity:
        available_entities = db_session.query(Entity.name).all()
        available_names = [e.name for e in available_entities]
        raise ValueError(f"Entity type '{entity_type}' not found. Available types: {available_names}")

    if cache is not None:
        cache[lookup_key] = entity.id
    return entity.id


def _normalize_synonyms(raw) -> set[str]:
    """Normalize synonyms from various formats into a set of clean strings."""
    if not raw:
        return set()
    if isinstance(raw, str):
        return {raw.strip()} if raw.strip() else set()
    if isinstance(raw, list):
        result = set()
        for s in raw:
            if s is None:
                continue
            cleaned = (s if isinstance(s, str) else str(s)).strip()
            if cleaned:
                result.add(cleaned)
        return result
    raise ValueError("Synonyms must be a string or a list of strings")


def _fetch_external_synonyms(
    *,
    has_gene_lookup: bool,
    source_db_name: str,
    entity_type: str,
    local_id: str,
    strain_id: str | None,
) -> set[str]:
    if has_gene_lookup and strain_id is not None:
        return set(fetch_ncbi_gene_synonyms(local_id, strain_id)) | set(fetch_uniprot_id(local_id, strain_id))

    if entity_type == "strain" and source_db_name.lower() == "aledb":
        print(f"Fetching NCBI assemblies for strain {local_id}...")
        ncbi_results = list(fetch_ncbi_assemblies(local_id))
        print(f"Found {len(ncbi_results)} assemblies for strain {local_id}.")
        return set(ncbi_results)
    return set()


def _process_batch(session, batch, source_db_cache, entity_type_cache):
    """Process a batch, returning (successful_count, failed_count)."""
    unique_payloads: dict[tuple[int, int, str], dict] = {}
    failures = 0

    for idx, entity in batch:
        try:
            has_gene_lookup = "gene_id" in entity and "strain_id" in entity
            required_fields = ["source_db", "gene_id", "strain_id"] if has_gene_lookup else ["source_db", "entity_type", "local_id"]
            for field in required_fields:
                if field not in entity:
                    raise ValueError(f"Missing required field: {field}")

            source_db_name = entity["source_db"]
            if has_gene_lookup:
                entity_type = validate_entity_type("gene")
                local_id = str(entity["gene_id"])
                strain_id = str(entity["strain_id"])
            else:
                entity_type = validate_entity_type(entity["entity_type"])
                local_id = entity["local_id"]
                strain_id = None

            source_db_id = get_source_db_id(session, source_db_name, cache=source_db_cache)
            entity_type_id = get_entity_type_id(session, entity_type, cache=entity_type_cache)
            uid = generate_uid(entity_type, local_id)

            synonyms = _normalize_synonyms(entity.get("synonyms")) | _fetch_external_synonyms(
                has_gene_lookup=has_gene_lookup,
                source_db_name=source_db_name,
                entity_type=entity_type,
                local_id=local_id,
                strain_id=strain_id,
            )

            key = (source_db_id, entity_type_id, local_id)
            if key in unique_payloads:
                unique_payloads[key]["synonyms"].update(synonyms)
            else:
                unique_payloads[key] = {
                    "source_db_id": source_db_id,
                    "entity_type_id": entity_type_id,
                    "local_id": local_id,
                    "uid": uid,
                    "synonyms": synonyms,
                }
        except Exception as exc:
            print(f"Error processing entity {idx}: {exc}")
            failures += 1

    if not unique_payloads:
        return 0, failures

    keys = list(unique_payloads.keys())
    existing_mappings = {
        (m.source_db_id, m.entity_type_id, m.local_id): m
        for m in session.query(Mapping).filter(
            tuple_(Mapping.source_db_id, Mapping.entity_type_id, Mapping.local_id).in_(keys)
        )  # type: ignore[arg-type]
    }
    existing_registries = {
        (r.source_db_id, r.entity_type_id, r.local_id): r
        for r in session.query(Registry).filter(
            tuple_(Registry.source_db_id, Registry.entity_type_id, Registry.local_id).in_(keys)
        )  # type: ignore[arg-type]
    }

    now = datetime.datetime.utcnow()
    new_registry_rows: list[dict] = []
    new_mapping_rows: list[dict] = []
    new_audit_rows: list[dict] = []
    new_synonym_audit_rows: list[dict] = []
    mapping_updates: list[dict] = []

    for key, payload in unique_payloads.items():
        source_db_id, entity_type_id, local_id = key

        if key not in existing_registries:
            new_registry_rows.append(
                {
                    "source_db_id": source_db_id,
                    "entity_type_id": entity_type_id,
                    "local_id": local_id,
                }
            )

        if key in existing_mappings:
            mapping_updates.append(
                {
                    "source_db_id": source_db_id,
                    "entity_type_id": entity_type_id,
                    "local_id": local_id,
                    "uid": payload["uid"],
                    "updated_at": now,
                }
            )
        else:
            new_mapping_rows.append(
                {
                    "source_db_id": source_db_id,
                    "entity_type_id": entity_type_id,
                    "local_id": local_id,
                    "uid": payload["uid"],
                    "updated_at": now,
                }
            )
            new_audit_rows.append(
                {
                    "uid": payload["uid"],
                    "event_type": "Ingest",
                }
            )

    if new_registry_rows:
        session.execute(insert(Registry), new_registry_rows)
    if new_mapping_rows:
        session.execute(insert(Mapping), new_mapping_rows)
    if new_audit_rows:
        session.execute(insert(AuditLog), new_audit_rows)
    if mapping_updates:
        session.execute(update(Mapping), mapping_updates)

    synonym_uids = {payload["uid"] for payload in unique_payloads.values() if payload["synonyms"]}
    new_synonym_rows: list[dict[str, str]] = []
    existing_synonyms: set[tuple[str, str]] = set()

    if synonym_uids:
        existing_synonym_rows = session.query(Synonym).filter(Synonym.uid.in_(synonym_uids)).all()
        existing_synonyms = {(row.uid, row.synonym) for row in existing_synonym_rows}

    for payload in unique_payloads.values():
        if not payload["synonyms"]:
            continue
        uid = payload["uid"]
        for synonym in payload["synonyms"]:
            key = (uid, synonym)
            if key not in existing_synonyms:
                existing_synonyms.add(key)
                new_synonym_rows.append({"uid": uid, "synonym": synonym})
                new_synonym_audit_rows.append(
                    {
                        "uid": uid,
                        "event_type": "Added synonym " + synonym,
                    }
                )

    if new_synonym_rows:
        session.execute(insert(Synonym), new_synonym_rows)
    if new_synonym_audit_rows:
        session.execute(insert(AuditLog), new_synonym_audit_rows)

    return len(unique_payloads), failures


def start_ingest(session, entities: list[dict], chunk_size: int = BATCH_SIZE) -> None:
    source_db_cache = build_source_db_cache(session)
    entity_type_cache = build_entity_type_cache(session)

    successful_ingests = 0
    failed_ingests = 0

    batch = []

    for idx, entity in enumerate(entities, 1):
        batch.append((idx, entity))

        if len(batch) >= chunk_size:
            success, failure = _process_batch(session, batch, source_db_cache, entity_type_cache)
            commit_with_retry(session)
            successful_ingests += success
            failed_ingests += failure
            batch.clear()

    if batch:
        success, failure = _process_batch(session, batch, source_db_cache, entity_type_cache)
        commit_with_retry(session)
        successful_ingests += success
        failed_ingests += failure

    print(
        f"Ingestion finished. Total processed: {successful_ingests + failed_ingests}. "
        f"Successful: {successful_ingests}, Failed: {failed_ingests}"
    )


def ingest_entities(file_path: Path):
    """Ingest all registry entries."""
    # Load JSON data
    try:
        with open(file_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{file_path}': {e}")
        sys.exit(1)

    if "entities" not in data:
        print("Error: JSON file must contain 'entities' key")
        sys.exit(1)

    entities = data["entities"]
    if not isinstance(entities, list):
        print("Error: 'entities' must be a list")
        sys.exit(1)

    session = get_session()

    print(f"Starting ingestion of {len(entities)} entities...")

    start_time = time.time()
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    start_ingest(session, entities)
    end_time = time.time()
    print(f"End time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")
    print(f"Ingestion completed in {end_time - start_time:.2f} seconds.")
