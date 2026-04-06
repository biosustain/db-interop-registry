"""MCP server exposing InteropDB Registry tools."""

import json
import httpx
from fastmcp import FastMCP

BASE_URL = "https://interopdb-staging-f-ca.salmonpebble-cac1724c.northeurope.azurecontainerapps.io"
TIMEOUT = 120.0

mcp = FastMCP(
    "InteropDB",
    instructions=(
        "You are a helpful assistant for querying the Interop DB Registry. "
        "Interop DB assigns unified identifiers to genes and strains across "
        "ALEdb, BiGGr, PanKB, and PMkbase, enabling cross-database queries."
    ),
)


def _get(path: str) -> dict:
    """Make a GET request to the InteropDB API."""
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        response = client.get(path)
        response.raise_for_status()
        return response.json()


@mcp.tool()
def get_gene(identifier: str) -> str:
    """Query a gene by local ID or UID.

    Args:
        identifier: Gene local ID (e.g. "rpoB") or UID (e.g. "G-6EE9A9CD8006").

    Returns the full registry item with local_id, uid, entity_type, and
    attributes from all source databases (ALEdb, BiGGr, PanKB).
    """
    try:
        result = _get(f"/gene/{identifier}")
        return json.dumps(result, indent=2, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return f"Error {e.response.status_code}: {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error: {e}"


@mcp.tool()
def get_strain(identifier: str) -> str:
    """Query a strain by local ID or UID.

    Args:
        identifier: Strain local ID (e.g. "511145") or UID (e.g. "S-6AC722234E99").

    Returns the full registry item with local_id, uid, entity_type, and
    attributes from all source databases (ALEdb, BiGGr, PanKB, PMkbase).
    """
    try:
        result = _get(f"/strain/{identifier}")
        return json.dumps(result, indent=2, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return f"Error {e.response.status_code}: {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error: {e}"


@mcp.tool()
def get_pair(gene_id: str, strain_id: str) -> str:
    """Query a gene-strain pair across all source databases.

    Args:
        gene_id: Gene local ID or UID.
        strain_id: Strain local ID or UID.

    Returns the pair result with gene, strain, and sources list containing
    data from each database (ALEdb, BiGGr, PanKB).
    """
    try:
        result = _get(f"/pair/{gene_id},{strain_id}")
        return json.dumps(result, indent=2, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return f"Error {e.response.status_code}: {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error: {e}"


@mcp.tool()
def search_entities(query: str = "") -> str:
    """Search entities in the registry by local ID, UID, or synonym.

    Args:
        query: Search term (e.g. "dnaA" or "511145"). Returns up to 200 matching results.

    Returns a list of matching entities with uid, local_id, entity_type,
    source_db, synonyms, and URLs.
    """
    try:
        params = {"q": query} if query else {}
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = client.get("/api/entities", params=params)
            response.raise_for_status()
            return json.dumps(response.json(), indent=2, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return f"Error {e.response.status_code}: {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error: {e}"


@mcp.tool()
def search_relationships(query: str = "") -> str:
    """Search gene-strain relationships by a gene or strain local ID or UID.

    For example, search by a gene to find all related strains, or by a strain
    to find all related genes.

    Args:
        query: A gene or strain local ID or UID (e.g. "rpoB" or "511145").
               Returns up to 200 matching results.

    Returns a list of gene-strain relationships with UIDs, local IDs,
    source database, and URLs.
    """
    try:
        params = {"q": query} if query else {}
        with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
            response = client.get("/api/relationships", params=params)
            response.raise_for_status()
            return json.dumps(response.json(), indent=2, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return f"Error {e.response.status_code}: {e.response.text}"
    except httpx.HTTPError as e:
        return f"Error: {e}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
