"""Ingest gene-strain relationships and URLs from external databases."""

import time

import requests
from sqlalchemy import func, tuple_
from sqlalchemy.dialects.postgresql import insert

from utils.db_connector import get_session
from utils.ingest import generate_uid, get_source_db_id, build_source_db_cache
from utils.models import AuditLog, EntityUrl, GeneStrainRelationship, RelationshipUrl, SourceDb


BATCH_SIZE = 5_000


def fetch_gene_strain_pairs(base_url: str) -> list[dict]:
    """
    Fetch gene-strain pairs from an external database API.

    Args:
        base_url: Base URL for the API endpoint

    Returns:
        List of dicts with 'gene' and 'strain' keys
    """
    try:
        response = requests.get(f"{base_url}/interop-query/gene-strain-pairs")
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            return data
        return data.get("pairs", [])
    except requests.RequestException as e:
        print(f"Error fetching gene-strain pairs from {base_url}: {e}")
        return []


def ingest_relationships(session, pairs: list[dict], source_db_name: str, source_db_cache: dict) -> tuple[int, int]:
    """
    Ingest gene-strain relationships into the database.

    Args:
        session: Database session
        pairs: List of dicts with 'gene' and 'strain' keys
        source_db_name: Name of the source database
        source_db_cache: Cache of source database IDs

    Returns:
        Tuple of (successful_count, failed_count)
    """
    if not pairs:
        return 0, 0

    source_db_id = get_source_db_id(session, source_db_name, cache=source_db_cache)

    prepared = []
    failures = 0

    for pair in pairs:
        try:
            gene_local_id = pair.get("gene")
            strain_local_id = pair.get("strain")

            if not gene_local_id or not strain_local_id:
                failures += 1
                continue

            gene_uid = generate_uid("gene", gene_local_id)
            strain_uid = generate_uid("strain", strain_local_id)

            prepared.append({
                "gene_uid": gene_uid,
                "strain_uid": strain_uid,
                "source_db_id": source_db_id,
            })
        except Exception as e:
            print(f"Error processing pair {pair}: {e}")
            failures += 1

    if not prepared:
        return 0, failures

    # Deduplicate
    unique_relationships: dict[tuple[str, str, int], dict] = {}
    for item in prepared:
        key = (item["gene_uid"], item["strain_uid"], item["source_db_id"])
        unique_relationships[key] = item

    keys = list(unique_relationships.keys())

    # Check existing relationships
    existing_keys = set()
    if keys:
        existing_rows = session.query(GeneStrainRelationship).filter(
            tuple_(
                GeneStrainRelationship.gene_uid,
                GeneStrainRelationship.strain_uid,
                GeneStrainRelationship.source_db_id
            ).in_(keys)
        ).all()
        existing_keys = {(r.gene_uid, r.strain_uid, r.source_db_id) for r in existing_rows}

    # Insert new relationships
    new_rows = []
    for key, payload in unique_relationships.items():
        if key not in existing_keys:
            new_rows.append(payload)

    if new_rows:
        session.bulk_insert_mappings(GeneStrainRelationship, new_rows)
        session.bulk_insert_mappings(AuditLog, [{
            "uid": f"{source_db_name}:relationships",
            "event_type": f"Ingest {len(new_rows)} gene-strain relationships",
        }])

    return len(unique_relationships), failures


def ingest_relationships_bulk(session, relationships: list[dict]) -> None:
    """
    Ingest gene-strain relationships from bulk data (already contains source_db).

    Args:
        session: Database session
        relationships: List of dicts with keys: gene_uid, strain_uid, source_db
    """
    if not relationships:
        return

    source_db_map = get_source_db_map(session)

    # Prepare records, generate UIDs
    prepared = []
    for rel in relationships:
        source_db_name = rel.get("source_db")
        source_db_id = source_db_map.get(source_db_name)
        if not source_db_id:
            print(f"Warning: Unknown source_db '{source_db_name}', skipping relationship")
            continue

        gene_uid = generate_uid("gene", rel["gene_uid"])
        strain_uid = generate_uid("strain", rel["strain_uid"])

        prepared.append({
            "gene_uid": gene_uid,
            "strain_uid": strain_uid,
            "source_db_id": source_db_id,
        })

    if not prepared:
        return

    # Use PostgreSQL upsert - on conflict do nothing (relationship already exists)
    stmt = insert(GeneStrainRelationship).values(prepared)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["gene_uid", "strain_uid", "source_db_id"]
    )
    session.execute(stmt)
    session.commit()
    print(f"Inserted {len(prepared)} gene-strain relationships (duplicates skipped)")


def ingest_bulk_relationships():
    """Ingest gene-strain relationships from all supported databases."""
    print("Ingesting gene-strain relationships from external databases...")

    session = get_session()
    source_db_cache = build_source_db_cache(session)

    databases = [
        ("https://pankb.org/", "Pankb"),
        # Add more databases here as they implement the gene-strain-pairs endpoint
        # ("https://aledb.org", "ALEdb"),
        # ("https://biggr.org/", "BiGGr"),
    ]

    total_success = 0
    total_failures = 0

    start_time = time.time()
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")

    for base_url, source_db_name in databases:
        print(f"Fetching gene-strain pairs from {source_db_name}...")
        pairs = fetch_gene_strain_pairs(base_url)
        print(f"Found {len(pairs)} pairs from {source_db_name}")

        if not pairs:
            continue

        # Process in batches
        for i in range(0, len(pairs), BATCH_SIZE):
            batch = pairs[i:i + BATCH_SIZE]
            success, failures = ingest_relationships(session, batch, source_db_name, source_db_cache)

            try:
                session.commit()
            except Exception:
                session.rollback()
                raise

            total_success += success
            total_failures += failures

            processed = i + len(batch)
            print(f"  Processed {processed}/{len(pairs)} pairs from {source_db_name}...")

    end_time = time.time()
    print(f"End time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")
    print(f"Ingestion completed in {end_time - start_time:.2f} seconds.")
    print(f"Total: {total_success} relationships ingested, {total_failures} failures")


def get_source_db_map(session) -> dict[str, int]:
    """Get mapping of source_db name to id."""
    source_dbs = session.query(SourceDb).all()
    return {db.db_name: db.id for db in source_dbs}


def ingest_entity_urls(session, entity_urls: list[dict]) -> None:
    """
    Ingest entity URLs into the entity_url table.
    Supports multiple URLs per entity (primary key now includes url).

    Args:
        session: SQLAlchemy session
        entity_urls: List of dicts with keys: uid, source_db, url_type, url
    """
    if not entity_urls:
        return

    source_db_map = get_source_db_map(session)

    # Prepare records for bulk insert
    records = []
    for url_data in entity_urls:
        source_db_name = url_data.get("source_db")
        source_db_id = source_db_map.get(source_db_name)
        if not source_db_id:
            print(f"Warning: Unknown source_db '{source_db_name}', skipping URL")
            continue

        records.append({
            "uid": url_data["uid"],
            "source_db_id": source_db_id,
            "url_type": url_data["url_type"],
            "url": url_data["url"],
        })

    if not records:
        return

    # Use PostgreSQL upsert - on conflict do nothing (url already exists for this entity)
    stmt = insert(EntityUrl).values(records)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["uid", "source_db_id", "url_type", "url"]
    )
    session.execute(stmt)
    session.commit()
    print(f"Inserted {len(records)} entity URLs (duplicates skipped)")


def ingest_relationship_urls(session, relationship_urls: list[dict]) -> None:
    """
    Ingest relationship URLs into the relationship_url table.
    Supports multiple URLs per relationship (primary key now includes url).

    Args:
        session: SQLAlchemy session
        relationship_urls: List of dicts with keys: gene_uid, strain_uid, source_db, url
    """
    if not relationship_urls:
        return

    source_db_map = get_source_db_map(session)

    # Prepare records for bulk insert
    records = []
    for url_data in relationship_urls:
        source_db_name = url_data.get("source_db")
        source_db_id = source_db_map.get(source_db_name)
        if not source_db_id:
            print(f"Warning: Unknown source_db '{source_db_name}', skipping relationship URL")
            continue

        # Generate UIDs for gene and strain
        gene_uid = generate_uid("gene", url_data["gene_uid"])
        strain_uid = generate_uid("strain", url_data["strain_uid"])

        records.append({
            "gene_uid": gene_uid,
            "strain_uid": strain_uid,
            "source_db_id": source_db_id,
            "url": url_data["url"],
        })

    if not records:
        return

    # Use PostgreSQL upsert - on conflict do nothing (url already exists for this relationship)
    stmt = insert(RelationshipUrl).values(records)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["gene_uid", "strain_uid", "source_db_id", "url"]
    )
    session.execute(stmt)
    session.commit()
    print(f"Inserted {len(records)} relationship URLs (duplicates skipped)")
