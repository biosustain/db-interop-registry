"""Tests for the InteropClient."""

import json
import tempfile
from pathlib import Path

import httpx
import pytest

from interopdb.client import InteropClient, InteropError


GENE_RESPONSE = {
    "local_id": "rpoB",
    "uid": "G-80D178D48AB8",
    "entity_type": "gene",
    "attributes": [
        {"source_db": "ALEdb", "local_id": "rpoB", "data": {"mutations": 42}},
    ],
}

STRAIN_RESPONSE = {
    "local_id": "511145",
    "uid": "S-6AC722234E99",
    "entity_type": "strain",
    "attributes": [
        {"source_db": "ALEdb", "local_id": "511145", "data": {}},
    ],
}

PAIR_RESPONSE = {
    "gene": "rpoB",
    "strain": "511145",
    "sources": [
        {"source": "aledb", "data": {"mutations": []}},
    ],
}


def _mock_transport(responses: dict[str, tuple[int, dict]]):
    """Create a mock transport that returns canned responses by URL path."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in responses:
            status, body = responses[path]
            return httpx.Response(status, json=body)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


class TestInteropClient:
    def test_get_gene(self):
        transport = _mock_transport({"/gene/rpoB": (200, GENE_RESPONSE)})
        client = InteropClient(base_url="http://test")
        client._client = httpx.Client(base_url="http://test", transport=transport)

        result = client.get_gene("rpoB")
        assert result["local_id"] == "rpoB"
        assert result["uid"] == "G-80D178D48AB8"
        assert result["entity_type"] == "gene"
        assert len(result["attributes"]) == 1

    def test_get_strain(self):
        transport = _mock_transport({"/strain/511145": (200, STRAIN_RESPONSE)})
        client = InteropClient(base_url="http://test")
        client._client = httpx.Client(base_url="http://test", transport=transport)

        result = client.get_strain("511145")
        assert result["local_id"] == "511145"
        assert result["entity_type"] == "strain"

    def test_get_pair(self):
        transport = _mock_transport({"/pair/rpoB,511145": (200, PAIR_RESPONSE)})
        client = InteropClient(base_url="http://test")
        client._client = httpx.Client(base_url="http://test", transport=transport)

        result = client.get_pair("rpoB", "511145")
        assert result["gene"] == "rpoB"
        assert result["strain"] == "511145"
        assert len(result["sources"]) == 1

    def test_not_found_raises(self):
        transport = _mock_transport({})
        client = InteropClient(base_url="http://test")
        client._client = httpx.Client(base_url="http://test", transport=transport)

        with pytest.raises(InteropError) as exc_info:
            client.get_gene("nonexistent")
        assert exc_info.value.status_code == 404

    def test_save_json(self, tmp_path):
        out = tmp_path / "result.json"
        InteropClient.save_json(GENE_RESPONSE, out)

        loaded = json.loads(out.read_text())
        assert loaded == GENE_RESPONSE

    def test_context_manager(self):
        transport = _mock_transport({"/gene/x": (200, GENE_RESPONSE)})
        with InteropClient(base_url="http://test") as client:
            client._client = httpx.Client(base_url="http://test", transport=transport)
            result = client.get_gene("x")
            assert result["local_id"] == "rpoB"
