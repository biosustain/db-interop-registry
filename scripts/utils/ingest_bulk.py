"""Ingest from internal databases."""

import re
import sys
import time

import requests
from utils.db_connector import get_session
from utils.ingest import start_ingest
from utils.ingest_relationships import ingest_relationships_bulk, ingest_entity_urls, ingest_relationship_urls


def get_entities(baseURL: str, sourceDB: str, genes: bool = True) -> dict:
    """
    Fetch strains and genes from API endpoints and format them as entities.
    Also collects URLs if the source database provides them.

    Args:
        baseURL: Base URL for the API endpoints
        sourceDB: Source database name (e.g., "ALEdb", "PMKbase", "Pankb")
        genes: Whether to fetch genes (some DBs don't have genes)

    Returns:
        Dictionary containing:
        - entities: list of entity objects with source_db, entity_type, and local_id
        - entity_urls: list of URL objects with uid, source_db, url_type, and url
    """
    entities = []
    entity_urls = []

    # Fetch strains
    try:
        strains_response = requests.get(f"{baseURL}/interop-query/strains")
        strains_response.raise_for_status()
        strains_data = strains_response.json()

        # Handle both formats: {"strains": [...]} and [...]
        if isinstance(strains_data, dict):
            strains_list = strains_data.get("strains", [])
        else:
            strains_list = strains_data

        # Add strain entities - handle both plain strings and dicts with URLs
        for strain in strains_list:
            if isinstance(strain, dict):
                # Format: {"strain": "id", "url": "..."}
                strain_id = strain.get("strain")
                url = strain.get("url")
                entities.append({"source_db": sourceDB, "entity_type": "strain", "local_id": strain_id})
                if url:
                    entity_urls.append({"uid": strain_id, "source_db": sourceDB, "url_type": "strain", "url": url})
            else:
                # Plain string format
                entities.append({"source_db": sourceDB, "entity_type": "strain", "local_id": strain})
    except requests.RequestException as e:
        print(f"Error fetching strains from {sourceDB}: {e}")

    if not genes:
        return {"entities": entities, "entity_urls": entity_urls}

    # Fetch genes
    try:
        genes_response = requests.get(f"{baseURL}/interop-query/genes")
        genes_response.raise_for_status()
        genes_data = genes_response.json()

        # Handle both formats: {"genes": [...]} and [...]
        if isinstance(genes_data, dict):
            genes_list = genes_data.get("genes", [])
        else:
            genes_list = genes_data

        # Track unique gene IDs to avoid duplicate entities
        seen_genes = set()

        # Add gene entities - handle both plain strings and dicts with URLs
        # Same gene may appear multiple times (different species), deduplicate entities but keep all URLs
        for gene in genes_list:
            if isinstance(gene, dict):
                # Format: {"gene": "id", "species": "xxx", "url": "..."}
                gene_id = gene.get("gene")
                url = gene.get("url")

                # Only add entity once per gene_id
                if gene_id and gene_id not in seen_genes:
                    entities.append({"source_db": sourceDB, "entity_type": "gene", "local_id": gene_id})
                    seen_genes.add(gene_id)

                # But collect all URLs (same gene can have multiple URLs for different species)
                if url:
                    entity_urls.append({"uid": gene_id, "source_db": sourceDB, "url_type": "gene", "url": url})
            else:
                # Plain string format
                if gene and gene not in seen_genes:
                    entities.append({"source_db": sourceDB, "entity_type": "gene", "local_id": gene})
                    seen_genes.add(gene)
    except requests.RequestException as e:
        print(f"Error fetching genes from {sourceDB}: {e}")

    return {"entities": entities, "entity_urls": entity_urls}


def ingest_gene_strain_pairs_streaming(session, baseURL: str, sourceDB: str, batch_size: int = 50000) -> dict:
    """
    Fetch and ingest gene-strain pairs in streaming mode (batch by batch).
    Each batch is written to DB immediately to reduce memory usage.

    Args:
        session: Database session
        baseURL: Base URL for the API endpoints
        sourceDB: Source database name
        batch_size: Number of records per request (default 50000)

    Returns:
        Dictionary with total counts
    """
    skip = 0
    total = None
    total_relationships = 0
    total_urls = 0

    try:
        while True:
            print(f"  Fetching pairs from {sourceDB}: skip={skip}, limit={batch_size}...")
            response = requests.get(
                f"{baseURL}/interop-query/gene-strain-pairs",
                params={"skip": skip, "limit": batch_size},
                timeout=300  # 5 minute timeout per request
            )
            response.raise_for_status()
            data = response.json()

            # Handle paginated response format
            if isinstance(data, dict) and "pairs" in data:
                pairs_list = data.get("pairs", [])
                total = data.get("total", 0)
                has_more = data.get("has_more", False)
            else:
                # Fallback for non-paginated response (legacy format)
                pairs_list = data if isinstance(data, list) else data.get("pairs", [])
                has_more = False

            # Process this batch - use dicts to deduplicate
            unique_relationships = {}  # key: (gene, strain) -> value: dict
            unique_urls = {}  # key: (gene, strain) -> value: dict

            for pair in pairs_list:
                gene = pair.get("gene")
                strain = pair.get("strain")
                url = pair.get("gene_strain_url")

                if gene and strain:
                    key = (gene, strain)
                    # Keep only one per (gene, strain) combination
                    if key not in unique_relationships:
                        unique_relationships[key] = {
                            "gene_uid": gene,
                            "strain_uid": strain,
                            "source_db": sourceDB
                        }
                    if url and key not in unique_urls:
                        unique_urls[key] = {
                            "gene_uid": gene,
                            "strain_uid": strain,
                            "source_db": sourceDB,
                            "url": url
                        }

            batch_relationships = list(unique_relationships.values())
            batch_urls = list(unique_urls.values())

            # Write this batch to DB immediately
            if batch_relationships:
                ingest_relationships_bulk(session, batch_relationships)
                total_relationships += len(batch_relationships)

            if batch_urls:
                ingest_relationship_urls(session, batch_urls)
                total_urls += len(batch_urls)

            fetched = len(pairs_list)
            print(f"  Ingested {fetched} pairs (total so far: {total_relationships}/{total or 'unknown'})")

            if not has_more or fetched == 0:
                break

            skip += batch_size

    except requests.RequestException as e:
        print(f"Error fetching gene-strain pairs from {sourceDB}: {e}")

    return {"total_relationships": total_relationships, "total_urls": total_urls}


def ingest_bulk_entities() -> None:
    """Ingest entities from internal databases."""

    print("Ingesting entities from internal databases...")

    # # Temporarily skip entities - only ingest pairs
    # all_entities = []
    # all_entity_urls = []

    # Define source databases
    sources = [
        {"url": "https://aledb.org", "name": "ALEdb", "genes": True, "pairs": False},
        {"url": "https://www.pmkbase.com", "name": "PMKbase", "genes": False, "pairs": False},
        {"url": "https://pankb.org", "name": "PanKB", "genes": True, "pairs": True},
        {"url": "https://biggr.org", "name": "Bigg", "genes": True, "pairs": False},
    ]

    # for source in sources:
    #     print(f"Fetching entities from {source['name']}...")
    #     result = get_entities(source["url"], source["name"], genes=source["genes"])
    #     all_entities.extend(result.get("entities", []))
    #     all_entity_urls.extend(result.get("entity_urls", []))

    # # Clean up gene local_ids
    # for entity in all_entities:
    #     if entity["entity_type"] == "strain":
    #         continue

    #     local_id = entity["local_id"]
    #     if local_id:
    #         if " " in local_id:
    #             local_id = local_id.split(" ")[0]
    #         local_id = re.sub(r"[^\w\-]", "", local_id)
    #         local_id = local_id.strip()
    #         entity["local_id"] = local_id

    # if not isinstance(all_entities, list):
    #     print("Error: 'entities' must be a list")
    #     sys.exit(1)

    session = get_session()
    start_time = time.time()

    # # Ingest entities
    # print(f"Starting ingestion of {len(all_entities)} entities...")
    # print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    # start_ingest(session, all_entities)
    # end_time = time.time()
    # print(f"Entity ingestion completed in {end_time - start_time:.2f} seconds.")

    # # Ingest entity URLs
    # if all_entity_urls:
    #     print(f"Ingesting {len(all_entity_urls)} entity URLs...")
    #     ingest_entity_urls(session, all_entity_urls)

    # Ingest gene-strain relationships (streaming mode - batch by batch)
    for source in sources:
        if source.get("pairs"):
            print(f"Fetching and ingesting gene-strain pairs from {source['name']} (streaming)...")
            result = ingest_gene_strain_pairs_streaming(session, source["url"], source["name"])
            print(f"  Completed: {result['total_relationships']} relationships, {result['total_urls']} URLs")

    total_time = time.time() - start_time
    print(f"Total ingestion completed in {total_time:.2f} seconds.")
