"""Helpers for working with UniProt data."""

from functools import lru_cache

import httpx

UNIPROT_API_URL = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_TIMEOUT = 30.0


@lru_cache(maxsize=2048)
def fetch_uniprot_id(gene: str, tax_id: str) -> tuple[str, ...]:
    """
    Fetch Reviewed (Swiss-Prot) UniProt Accession IDs for a gene and taxonomy ID.
    
    Args:
        gene: The gene name (e.g., 'rpoB').
        tax_id: The taxonomy ID (e.g., '1590').
        
    Returns:
        A tuple of UniProt Accession strings (e.g., ('Q88XZ3',)).
    """
    gene_str = str(gene).strip()
    tax_id_str = str(tax_id).strip()

    if not gene_str or not tax_id_str:
        return ()

    # specific query for exact gene match, specific taxonomy, and only reviewed entries
    query = f"gene_exact:{gene_str} AND taxonomy_id:{tax_id_str} AND reviewed:true"

    params = {
        "query": query,
        "fields": "accession",
        "format": "json"
    }

    try:
        with httpx.Client(timeout=UNIPROT_TIMEOUT) as client:
            resp = client.get(UNIPROT_API_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
            
    except httpx.HTTPError as exc:
        print(
            f"Warning: failed to fetch UniProt ID for gene '{gene_str}' and tax_id '{tax_id_str}': {exc}"
        )
        return ()
    except ValueError:
        return ()

    results = payload.get("results", [])
    
    cleaned: list[str] = []
    for item in results:
        accession = item.get("primaryAccession")
        if accession:
            cleaned_val = str(accession).strip()
            if cleaned_val:
                cleaned.append(cleaned_val)

    return tuple(cleaned)