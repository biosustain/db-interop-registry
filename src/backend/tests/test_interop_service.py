import httpx
import pytest

from backend.interop.services.interop import InteropService


@pytest.mark.parametrize(
    ("source_id", "method_name"),
    [
        (1, "_fetch_from_biggr"),
        (2, "_fetch_from_aledb"),
        (3, "_fetch_from_pmkbase"),
        (4, "_fetch_from_pankb"),
    ],
)
def test_fetch_attributes_routes_to_expected_backend(monkeypatch, source_id, method_name):
    calls: list[tuple[int, str]] = []

    def stub(entity_type_id: int, local_id: str) -> dict[str, str]:
        calls.append((entity_type_id, local_id))
        return {"source": method_name, "local_id": local_id}

    monkeypatch.setattr(InteropService, method_name, staticmethod(stub))

    result = InteropService.fetch_attributes(source_id, 2, "ID-42")

    assert result == {"source": method_name, "local_id": "ID-42"}
    assert calls == [(2, "ID-42")]


def test_fetch_attributes_returns_empty_for_unknown_source():
    result = InteropService.fetch_attributes(999, 1, "ID-1")
    assert result == {}


def test_fetch_attributes_wraps_http_errors(monkeypatch):
    def raise_error(entity_type_id: int, local_id: str):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(InteropService, "_fetch_from_biggr", staticmethod(raise_error))

    result = InteropService.fetch_attributes(1, 1, "ID-1")

    assert result == {"error": "interop request failed: boom"}


@pytest.mark.parametrize(
    ("method_name", "prefix"),
    [
        ("_fetch_from_biggr", "http://biggr-prod.northeurope.cloudapp.azure.com/interop-query/query-by-"),
        ("_fetch_from_aledb", "https://aledb.org/interop-query/query-by-"),
        ("_fetch_from_pmkbase", "https://pmkbase.com/interop-query/query-by-"),
        ("_fetch_from_pankb", "http://pankb-preprod.northeurope.cloudapp.azure.com/interop-query/query-by-"),
    ],
)
@pytest.mark.parametrize("entity_type_id, endpoint", [(1, "gene"), (2, "strain")])
def test_backend_fetches_call_make_request(monkeypatch, method_name, prefix, entity_type_id, endpoint):
    recorded: dict[str, str] = {}

    def fake_request(url: str, local_id: str) -> dict[str, str]:
        recorded["url"] = url
        recorded["local_id"] = local_id
        return {"ok": True}

    monkeypatch.setattr(InteropService, "_make_request", staticmethod(fake_request))

    method = getattr(InteropService, method_name)
    result = method(entity_type_id, "LOC-1")

    assert result == {"ok": True}
    assert recorded == {"url": f"{prefix}{endpoint}", "local_id": "LOC-1"}


@pytest.mark.parametrize(
    "method_name",
    [
        "_fetch_from_biggr",
        "_fetch_from_aledb",
        "_fetch_from_pmkbase",
        "_fetch_from_pankb",
    ],
)
def test_backend_fetches_ignore_unknown_entity_type(monkeypatch, method_name):
    def unexpected_call(url: str, local_id: str):
        raise AssertionError("Request helper should not be invoked for invalid entity type")

    monkeypatch.setattr(InteropService, "_make_request", staticmethod(unexpected_call))

    method = getattr(InteropService, method_name)
    assert method(99, "LOC-2") == {}


def test_make_request_posts_expected_payload(monkeypatch):
    calls: dict[str, object] = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            calls["raise_called"] = True

        def json(self) -> dict[str, str]:
            return {"status": "ok"}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            calls["client_args"] = args
            calls["client_kwargs"] = kwargs

        def __enter__(self):
            calls["enter"] = True
            return self

        def __exit__(self, exc_type, exc, tb):
            calls["exit"] = True

        def post(self, url: str, json: dict[str, object], headers: dict[str, str]) -> DummyResponse:
            calls["post"] = {"url": url, "json": json, "headers": headers}
            return DummyResponse()

    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: DummyClient(*args, **kwargs))

    result = InteropService._make_request("http://example.com/resource", "L-55")

    assert result == {"status": "ok"}
    assert calls["client_kwargs"] == {"timeout": 120}
    assert calls["post"]["url"] == "http://example.com/resource"
    assert calls["post"]["json"] == {"ids": ["L-55"]}
    assert calls["post"]["headers"] == {"Accept": "application/json"}
    assert calls["raise_called"] is True
    assert calls["enter"] is True and calls["exit"] is True


def test_make_pair_request_posts_pair_payload(monkeypatch):
    calls: dict[str, object] = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            calls["raise_called"] = True

        def json(self) -> dict[str, str]:
            return {"status": "pair-ok"}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            calls["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            calls["exit"] = True

        def post(self, url: str, json: dict[str, object], headers: dict[str, str]) -> DummyResponse:
            calls["post"] = {"url": url, "json": json, "headers": headers}
            return DummyResponse()

    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: DummyClient(*args, **kwargs))

    result = InteropService._make_pair_request("http://example.com/pairs", "G-1", "S-2")

    assert result == {"status": "pair-ok"}
    assert calls["client_kwargs"] == {"timeout": 120}
    assert calls["post"]["json"] == {"pairs": [{"gene": "G-1", "strain": "S-2"}]}
    assert calls["post"]["headers"] == {"Accept": "application/json"}
    assert calls["exit"] is True and calls["raise_called"] is True


def test_fetch_pair_attributes_collects_results(monkeypatch):
    def fake_pair_request(url: str, gene_id: str, strain_id: str) -> dict[str, str]:
        return {"url": url, "gene": gene_id, "strain": strain_id}

    monkeypatch.setattr(InteropService, "_make_pair_request", staticmethod(fake_pair_request))

    result = InteropService.fetch_pair_attributes("GENE-1", "STRAIN-9")

    assert result["gene"] == "GENE-1"
    assert result["strain"] == "STRAIN-9"
    assert {entry["source"] for entry in result["sources"]} == {"biggr", "aledb", "pankb"}
    assert all(entry["data"]["gene"] == "GENE-1" for entry in result["sources"])


def test_fetch_pair_attributes_handles_http_errors(monkeypatch):
    def fake_pair_request(url: str, gene_id: str, strain_id: str):
        if "aledb" in url:
            raise httpx.HTTPError("offline")
        return {"url": url}

    monkeypatch.setattr(InteropService, "_make_pair_request", staticmethod(fake_pair_request))

    result = InteropService.fetch_pair_attributes("GENE-1", "STRAIN-9")

    error_entry = next(item for item in result["sources"] if item["source"] == "aledb")
    assert error_entry["data"] == {"error": "interop request failed: offline"}
    ok_entries = [item for item in result["sources"] if item["source"] != "aledb"]
    assert all(entry["data"] == {"url": entry["data"]["url"]} for entry in ok_entries)
