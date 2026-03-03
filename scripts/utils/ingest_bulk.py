"""Ingest from internal databases."""

import time

import requests
from utils.db_connector import get_session
from utils.ingest import start_ingest
from utils.ingest_relationships import (
    get_source_db_map,
    get_source_db_map,
    ingest_entity_urls,
    ingest_relationship_urls,
    ingest_relationships_bulk,
)


def ingest_strains(session, baseURL: str, sourceDB: str, source_db_map: dict[str, int], batch_size: int = 10000) -> tuple[int, int]:
    """
    Fetch and ingest strains from a source database (paginated).
    The API is expected to return:
        {"strains": [...], "skip": int, "limit": int, "has_more": bool, "total"?: int}

    Args:
        session: Database session
        baseURL: Base URL for the API endpoints
        sourceDB: Source database name
        batch_size: Number of records per HTTP request (default 10000)

    Returns:
        (total_fetched, total_urls)
    """
    skip = 0
    total_fetched = 0
    total_urls = 0

    try:
        while True:
            response = requests.get(
                f"{baseURL}/interop-query/strains",
                params={"skip": skip, "limit": batch_size},
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()

            strains_list = data.get("strains", []) if isinstance(data, dict) else data
            has_more = data.get("has_more", False) if isinstance(data, dict) else False

            entities = []
            entity_urls = []
            for strain in strains_list:
                if isinstance(strain, dict):
                    strain_id = strain.get("strain")
                    url = strain.get("url")
                else:
                    strain_id = strain
                    url = None
                if strain_id:
                    entities.append({"source_db": sourceDB, "entity_type": "strain", "local_id": strain_id})
                    if url:
                        entity_urls.append({"local_id": strain_id, "source_db": sourceDB, "url_type": "strain", "url": url})

            if entities:
                start_ingest(session, entities)
            if entity_urls:
                ingest_entity_urls(session, entity_urls, source_db_map)

            total_fetched += len(strains_list)
            total_urls += len(entity_urls)

            if not has_more or len(strains_list) == 0:
                break

            skip += batch_size

    except requests.RequestException as e:
        print(f"Error fetching strains from {sourceDB}: {e}")

    return total_fetched, total_urls


def ingest_genes(session, baseURL: str, sourceDB: str, source_db_map: dict[str, int], batch_size: int = 10000) -> tuple[int, int]:
    """
    Fetch and ingest genes from a source database (paginated).
    The API is expected to return:
        {"genes": [...], "skip": int, "limit": int, "has_more": bool, "total"?: int}

    Args:
        session: Database session
        baseURL: Base URL for the API endpoints
        sourceDB: Source database name
        batch_size: Number of records per HTTP request (default 10000)

    Returns:
        (total_fetched, total_urls)
    """
    skip = 0
    total_fetched = 0
    total_urls = 0

    try:
        while True:
            response = requests.get(
                f"{baseURL}/interop-query/genes",
                params={"skip": skip, "limit": batch_size},
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()

            genes_list = data.get("genes", []) if isinstance(data, dict) else data
            has_more = data.get("has_more", False) if isinstance(data, dict) else False

            entities = []
            entity_urls = []
            for gene in genes_list:
                if isinstance(gene, dict):
                    gene_id = gene.get("gene")
                    url = gene.get("url")
                else:
                    gene_id = gene
                    url = None
                if gene_id:
                    entities.append({"source_db": sourceDB, "entity_type": "gene", "local_id": gene_id})
                if gene_id and url:
                    entity_urls.append({"local_id": gene_id, "source_db": sourceDB, "url_type": "gene", "url": url})

            if entities:
                start_ingest(session, entities)
            if entity_urls:
                ingest_entity_urls(session, entity_urls, source_db_map)

            total_fetched += len(genes_list)
            total_urls += len(entity_urls)

            if not has_more or len(genes_list) == 0:
                break

            skip += batch_size

    except requests.RequestException as e:
        print(f"Error fetching genes from {sourceDB}: {e}")

    return total_fetched, total_urls


def ingest_gene_strain_pairs(session, baseURL: str, sourceDB: str, source_db_map: dict[str, int], batch_size: int = 100000) -> tuple[int, int]:
    """
    Fetch and ingest gene-strain pairs from a source database (paginated).
    The API is expected to return:
        {"pairs": [...], "skip": int, "limit": int, "has_more": bool, "total"?: int}

    Args:
        session: Database session
        baseURL: Base URL for the API endpoints
        sourceDB: Source database name
        batch_size: Number of records per HTTP request (default 10000)

    Returns:
        (total_pairs_fetched, total_urls)
    """
    skip = 0
    total_pairs_fetched = 0
    total_urls = 0

    try:
        while True:
            response = requests.get(
                f"{baseURL}/interop-query/gene-strain-pairs",
                params={"skip": skip, "limit": batch_size},
                timeout=300
            )
            response.raise_for_status()
            data = response.json()

            pairs_list = data.get("pairs", [])
            has_more = data.get("has_more", False)

            relationships = []
            relationship_urls = []
            for pair in pairs_list:
                gene = pair.get("gene")
                strain = pair.get("strain")
                url = pair.get("url") or pair.get("gene_strain_url")

                if gene and strain:
                    relationships.append({"gene_local_id": gene, "strain_local_id": strain, "source_db": sourceDB})
                    if url:
                        relationship_urls.append({"gene_local_id": gene, "strain_local_id": strain, "source_db": sourceDB, "url": url})

            if relationships:
                ingest_relationships_bulk(session, relationships, source_db_map)
            if relationship_urls:
                ingest_relationship_urls(session, relationship_urls, source_db_map)

            total_pairs_fetched += len(pairs_list)
            total_urls += len(relationship_urls)

            if not has_more or len(pairs_list) == 0:
                break

            skip += batch_size

    except requests.RequestException as e:
        print(f"Error fetching gene-strain pairs from {sourceDB}: {e}")

    return total_pairs_fetched, total_urls


def ingest_bulk_entities() -> None:
    """Ingest entities from internal databases."""

    print("Ingesting entities from internal databases...")

    # Define source databases
    sources = [
        {"url": "https://aledb.org", "name": "ALEdb", "genes": True, "pairs": False},
        {"url": "https://www.pmkbase.com", "name": "PMKbase", "genes": False, "pairs": False},
        {"url": "https://pankb.org", "name": "PanKB", "genes": True, "pairs": True},
        {"url": "https://biggr.org", "name": "BiGGr", "genes": True, "pairs": False},
    ]

    session = get_session()
    source_db_map = get_source_db_map(session)
    start_time = time.time()
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")

    for source in sources:
        # print(f"Start ingesting from {source['name']}...")
        fetched, urls = ingest_strains(session, source["url"], source["name"], source_db_map)
        # print(f"  Strains: fetched {fetched}, URLs {urls}")

        # if source.get("genes"):
            fetched, urls = ingest_genes(session, source["url"], source["name"], source_db_map)
            # print(f"  Genes: fetched {fetched}, URLs {urls}")

        if source.get("pairs"):
            fetched, urls = ingest_gene_strain_pairs(session, source["url"], source["name"], source_db_map)
            print(f"  Pairs: fetched {fetched}, URLs {urls}")

    total_time = time.time() - start_time
    print(f"Total ingestion completed in {total_time:.2f} seconds.")
