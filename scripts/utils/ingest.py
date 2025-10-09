"""Ingest utilities."""

import datetime
import hashlib
import json
import sys
from pathlib import Path

from utils.db_connector import get_session
from utils.models import Entity, Mapping, Registry, SourceDb


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
    hash_digest = hashlib.sha256(hash_input).hexdigest()[:8]

    # Add appropriate prefix
    prefix = "G-" if entity_type.lower() == "gene" else "S-"
    return f"{prefix}{hash_digest.upper()}"


def get_source_db_id(db_session, db_name: str) -> int:
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
    print(f"Looking up source database ID for '{db_name}'...")
    source_db = db_session.query(SourceDb).filter(SourceDb.db_name == db_name).first()

    if not source_db:
        print(f"Error: Source database '{db_name}' not found in the database.")
        available_dbs = db_session.query(SourceDb.db_name).all()
        available_names = [db.db_name for db in available_dbs]
        raise ValueError(f"Source database '{db_name}' not found. Available databases: {available_names}")

    return source_db.id


def get_entity_type_id(db_session, entity_type: str) -> int:
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
    entity = db_session.query(Entity).filter(Entity.name.ilike(entity_type)).first()
    if not entity:
        available_entities = db_session.query(Entity.name).all()
        available_names = [e.name for e in available_entities]
        raise ValueError(f"Entity type '{entity_type}' not found. Available types: {available_names}")

    return entity.id


def start_ingest(session, entities: list) -> None:
    try:
        successful_ingests = 0
        failed_ingests = 0

        for i, entity in enumerate(entities, 1):
            try:
                required_fields = ["source_db", "entity_type", "local_id"]
                for field in required_fields:
                    if field not in entity:
                        raise ValueError(f"Missing required field: {field}")

                source_db_name = entity["source_db"]
                entity_type = validate_entity_type(entity["entity_type"])
                local_id = entity["local_id"]

                print(f"Processing entity {i}/{len(entities)}: {source_db_name} | {entity_type} | {local_id}")

                source_db_id = get_source_db_id(session, source_db_name)
                entity_type_id = get_entity_type_id(session, entity_type)

                # Generate UID
                uid = generate_uid(entity_type, local_id)
                print(f"   Generated UID: {uid}")

                # Check if registry entry already exists
                existing_registry = (
                    session.query(Registry)
                    .filter(
                        Registry.source_db_id == source_db_id,
                        Registry.entity_type_id == entity_type_id,
                        Registry.local_id == local_id,
                    )
                    .first()
                )

                if existing_registry:
                    print("Registry entry already exists...")
                else:
                    # Create registry entry
                    registry_entry = Registry(
                        source_db_id=source_db_id, entity_type_id=entity_type_id, local_id=local_id
                    )

                    session.add(registry_entry)
                    print("Added to registry table")

                # Check if mapping already exists
                existing_mapping = (
                    session.query(Mapping)
                    .filter(
                        Mapping.source_db_id == source_db_id,
                        Mapping.entity_type_id == entity_type_id,
                        Mapping.local_id == local_id,
                    )
                    .first()
                )

                if existing_mapping:
                    # Update existing mapping
                    existing_mapping.uid = uid
                    existing_mapping.updated_at = datetime.datetime.now(datetime.UTC)
                    print("   Updated existing mapping")
                else:
                    # Create new mapping entry
                    mapping_entry = Mapping(
                        source_db_id=source_db_id, entity_type_id=entity_type_id, local_id=local_id, uid=uid
                    )
                    session.add(mapping_entry)
                    print("Added to mapping table")

                # Commit this entity
                session.commit()
                successful_ingests += 1
                print(f"Entity {i} ingested successfully!")
            except Exception as e:
                print(f"Error processing entity {i}: {e}")
                failed_ingests += 1
                continue
    except Exception as e:
        print(f"Fatal error during ingestion: {e}")
        sys.exit(1)

    finally:
        session.close()


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
    start_ingest(session, entities)
