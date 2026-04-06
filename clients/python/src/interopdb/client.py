"""Interop DB Registry API client."""

import json
from pathlib import Path

import httpx

DEFAULT_BASE_URL = "https://interopdb-staging-f-ca.salmonpebble-cac1724c.northeurope.azurecontainerapps.io"
DEFAULT_TIMEOUT = 120.0


class InteropError(Exception):
    """Raised when an API request fails."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class InteropClient:
    """Client for querying the Interop DB Registry API.

    Args:
        base_url: Base URL of the Interop DB server.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def get_gene(self, identifier: str) -> dict:
        """Query a gene by local ID or UID.

        Args:
            identifier: Gene local ID (e.g. ``"rpoB"``) or UID (e.g. ``"G-6EE9A9CD8006"``).

        Returns:
            Registry item with ``local_id``, ``uid``, ``entity_type``, and ``attributes`` from all source databases.
        """
        return self._get(f"/gene/{identifier}")

    def get_strain(self, identifier: str) -> dict:
        """Query a strain by local ID or UID.

        Args:
            identifier: Strain local ID (e.g. ``"511145"``) or UID (e.g. ``"S-6AC722234E99"``).

        Returns:
            Registry item with ``local_id``, ``uid``, ``entity_type``, and ``attributes`` from all source databases.
        """
        return self._get(f"/strain/{identifier}")

    def get_pair(self, gene_id: str, strain_id: str) -> dict:
        """Query a gene-strain pair across all source databases.

        Args:
            gene_id: Gene local ID or UID.
            strain_id: Strain local ID or UID.

        Returns:
            Pair result with ``gene``, ``strain``, and ``sources`` list containing data from each database.
        """
        return self._get(f"/pair/{gene_id},{strain_id}")

    def search_entities(self, query: str = "") -> dict:
        """Search entities by local ID, UID, or synonym.

        Args:
            query: Search term (e.g. ``"dnaA"``). Empty string returns default results.
                   Returns up to 200 matching results.

        Returns:
            Dictionary with ``entities`` list, ``total`` (registry total),
            ``gene_count``, ``strain_count``, and when searching,
            ``result_gene_count`` and ``result_strain_count``.
        """
        params = {"q": query} if query else {}
        response = self._client.get("/api/entities", params=params)
        if response.status_code == 200:
            return response.json()
        detail = response.text or response.reason_phrase
        raise InteropError(response.status_code, detail)

    def search_relationships(self, query: str = "") -> dict:
        """Search gene-strain relationships by a single entity's local ID or UID.

        For example, search by a gene to find all related strains, or by a strain
        to find all related genes.

        Args:
            query: A gene or strain local ID or UID (e.g. ``"rpoB"`` or ``"511145"``).
                   Empty string returns default results. Returns up to 200 matching results.

        Returns:
            Dictionary with ``relationships`` list and ``total`` (registry total).
        """
        params = {"q": query} if query else {}
        response = self._client.get("/api/relationships", params=params)
        if response.status_code == 200:
            return response.json()
        detail = response.text or response.reason_phrase
        raise InteropError(response.status_code, detail)

    def _get(self, path: str) -> dict:
        response = self._client.get(path)
        if response.status_code == 200:
            return response.json()
        detail = response.text or response.reason_phrase
        raise InteropError(response.status_code, detail)

    @staticmethod
    def save_json(data: dict, path: str | Path) -> None:
        """Save a result dictionary to a JSON file.

        Args:
            data: Result from ``get_gene``, ``get_strain``, or ``get_pair``.
            path: Output file path.
        """
        path = Path(path)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
