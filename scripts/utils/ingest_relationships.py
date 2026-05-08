"""Ingest gene-strain relationships and URLs from external databases."""

from sqlalchemy.dialects.postgresql import insert
from utils.db_connector import execute_with_retry
from utils.ingest import generate_uid
from utils.models import EntityUrl, GeneStrainRelationship, RelationshipUrl, SourceDb


def ingest_relationships_bulk(session, relationships: list[dict], source_db_map: dict[str, int]) -> int:
    """
    Ingest gene-strain relationships from bulk data (already contains source_db).

    Args:
        session: Database session
        relationships: List of dicts with keys: gene_local_id, strain_local_id, source_db
        source_db_map: Mapping of source_db name to id

    Returns:
        Number of unique relationships submitted (before DB conflict check)
    """
    if not relationships:
        return 0

    unique_records: dict[tuple, dict] = {}
    for rel in relationships:
        source_db_name = rel.get("source_db")
        source_db_id = source_db_map.get(source_db_name)
        if not source_db_id:
            print(f"Warning: Unknown source_db '{source_db_name}', skipping relationship")
            continue

        gene_uid = generate_uid("gene", rel["gene_local_id"])
        strain_uid = generate_uid("strain", rel["strain_local_id"])

        key = (gene_uid, strain_uid, source_db_id)
        unique_records[key] = {
            "gene_uid": gene_uid,
            "strain_uid": strain_uid,
            "source_db_id": source_db_id,
        }

    prepared = list(unique_records.values())

    if not prepared:
        return 0

    # Use PostgreSQL upsert - on conflict do nothing (relationship already exists)
    stmt = insert(GeneStrainRelationship).values(prepared)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["gene_uid", "strain_uid", "source_db_id"]
    )
    execute_with_retry(session, stmt)
    return len(prepared)


def get_source_db_map(session) -> dict[str, int]:
    """Get mapping of source_db name to id."""
    source_dbs = session.query(SourceDb).all()
    return {db.db_name: db.id for db in source_dbs}


def ingest_entity_urls(session, entity_urls: list[dict], source_db_map: dict[str, int]) -> int:
    """
    Ingest entity URLs into the entity_url table.
    Supports multiple URLs per entity (primary key now includes url).

    Args:
        session: SQLAlchemy session
        entity_urls: List of dicts with keys: local_id, source_db, url_type, url
        source_db_map: Mapping of source_db name to id

    Returns:
        Number of unique URLs submitted (before DB conflict check)
    """
    if not entity_urls:
        return 0

    # Prepare records for bulk insert, deduplicating by primary key within the batch
    unique_records: dict[tuple, dict] = {}
    for url_data in entity_urls:
        source_db_name = url_data.get("source_db")
        source_db_id = source_db_map.get(source_db_name)
        if not source_db_id:
            print(f"Warning: Unknown source_db '{source_db_name}', skipping URL")
            continue

        record = {
            "local_id": url_data["local_id"],
            "source_db_id": source_db_id,
            "url_type": url_data["url_type"],
            "url": url_data["url"],
        }
        key = (record["local_id"], record["source_db_id"], record["url_type"], record["url"])
        unique_records[key] = record

    records = list(unique_records.values())

    if not records:
        return 0

    # Use PostgreSQL upsert - on conflict do nothing (url already exists for this entity)
    stmt = insert(EntityUrl).values(records)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["local_id", "source_db_id", "url_type", "url"]
    )
    execute_with_retry(session, stmt)
    return len(records)


def ingest_relationship_urls(session, relationship_urls: list[dict], source_db_map: dict[str, int]) -> int:
    """
    Ingest relationship URLs into the relationship_url table.
    Supports multiple URLs per relationship (primary key now includes url).

    Args:
        session: SQLAlchemy session
        relationship_urls: List of dicts with keys: gene_local_id, strain_local_id, source_db, url
        source_db_map: Mapping of source_db name to id

    Returns:
        Number of unique URLs submitted (before DB conflict check)
    """
    if not relationship_urls:
        return 0

    unique_records: dict[tuple, dict] = {}
    for url_data in relationship_urls:
        source_db_name = url_data.get("source_db")
        source_db_id = source_db_map.get(source_db_name)
        if not source_db_id:
            print(f"Warning: Unknown source_db '{source_db_name}', skipping relationship URL")
            continue

        gene_uid = generate_uid("gene", url_data["gene_local_id"])
        strain_uid = generate_uid("strain", url_data["strain_local_id"])

        record = {
            "gene_uid": gene_uid,
            "strain_uid": strain_uid,
            "source_db_id": source_db_id,
            "url": url_data["url"],
        }
        key = (record["gene_uid"], record["strain_uid"], record["source_db_id"], record["url"])
        unique_records[key] = record

    records = list(unique_records.values())

    if not records:
        return 0

    # Use PostgreSQL upsert - on conflict do nothing (url already exists for this relationship)
    stmt = insert(RelationshipUrl).values(records)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["gene_uid", "strain_uid", "source_db_id", "url"]
    )
    execute_with_retry(session, stmt)
    return len(records)
