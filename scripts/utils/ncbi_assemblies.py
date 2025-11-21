"""Helpers for working with NCBI data."""

from functools import lru_cache

import httpx

NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
NCBI_ESEARCH_URL = f"{NCBI_BASE_URL}/esearch.fcgi"
NCBI_ESUMMARY_URL = f"{NCBI_BASE_URL}/esummary.fcgi"
NCBI_ASSEMBLY_TERM = "txid{local_id}[Organism:noexp]"
NCBI_TIMEOUT = 30.0
ESEARCH_PAGE_SIZE = 500  # IDs returned per search page
ESUMMARY_BATCH_SIZE = 200  # IDs resolved to accession strings per call


@lru_cache(maxsize=2048)
def fetch_ncbi_assemblies(local_id: str) -> tuple[str, ...]:
    """
    Fetch Assembly Accessions (GCF_..., GCA_...) for a taxonomy ID by searching db=assembly.
    """
    local_id_str = str(local_id).strip()
    if not local_id_str:
        return ()

    search_params = {
        "db": "assembly",
        "retmode": "json",
        "term": NCBI_ASSEMBLY_TERM.format(local_id=local_id_str),
    }

    assembly_uids: list[str] = []
    retstart = 0
    expected_total = None

    try:
        with httpx.Client(timeout=NCBI_TIMEOUT) as client:
            while expected_total is None or retstart < expected_total:
                retmax = ESEARCH_PAGE_SIZE
                if expected_total is not None:
                    retmax = max(1, min(retmax, expected_total - retstart))

                query_params = search_params | {"retmax": retmax, "retstart": retstart}

                resp = client.get(NCBI_ESEARCH_URL, params=query_params)
                resp.raise_for_status()

                try:
                    payload = resp.json()
                except ValueError:
                    break  # JSON parse failure

                esearch = payload.get("esearchresult") or {}

                if expected_total is None:
                    try:
                        expected_total = int(esearch.get("count", "0"))
                    except ValueError:
                        expected_total = 0

                id_list = esearch.get("idlist") or []
                if not id_list:
                    break

                assembly_uids.extend(id_list)
                retstart += len(id_list)

            if not assembly_uids:
                return ()

            final_accessions = []

            for i in range(0, len(assembly_uids), ESUMMARY_BATCH_SIZE):
                chunk = assembly_uids[i : i + ESUMMARY_BATCH_SIZE]
                ids_str = ",".join(chunk)

                summary_params = {
                    "db": "assembly",
                    "retmode": "json",
                    "id": ids_str,
                }

                resp = client.get(NCBI_ESUMMARY_URL, params=summary_params)
                resp.raise_for_status()

                summary_data = resp.json()
                result_data = summary_data.get("result", {})

                for uid in chunk:
                    item = result_data.get(uid)
                    if item:
                        acc = item.get("assemblyaccession")
                        if acc:
                            final_accessions.append(acc)

            return tuple(final_accessions)

    except httpx.HTTPError as exc:
        print(f"Warning: failed to fetch assemblies for taxid {local_id_str}: {exc}")
        return ()


@lru_cache(maxsize=2048)
def fetch_ncbi_gene_synonyms(gene_id: str, strain_id: str) -> tuple[str, ...]:
    """Fetch NCBI gene identifiers for a gene constrained to a specific organism taxonomy ID."""
    gene_id_str = str(gene_id).strip()
    strain_id_str = str(strain_id).strip()
    if not gene_id_str or not strain_id_str:
        return ()

    search_params = {
        "db": "gene",
        "retmode": "json",
        "term": f"{gene_id_str}[All Fields] AND txid{strain_id_str}[Organism:noexp]",
    }

    try:
        with httpx.Client(timeout=NCBI_TIMEOUT) as client:
            resp = client.get(NCBI_ESEARCH_URL, params=search_params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        print(
            f"Warning: failed to fetch gene synonyms for gene '{gene_id_str}' and strain '{strain_id_str}': {exc}"
        )
        return ()
    except ValueError:
        return ()

    esearch = payload.get("esearchresult") or {}
    id_list = esearch.get("idlist") or []

    cleaned: list[str] = []
    for value in id_list:
        cleaned_value = str(value).strip()
        if cleaned_value:
            cleaned.append(cleaned_value)

    return tuple(cleaned)
