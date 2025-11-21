import pytest

from backend.interop.models import Entity, Mapping, Registry, SourceDb, Synonym
from backend.interop.services.registry import RegistryService
from backend.interop.utils.exceptions import (
    DatabaseInconsistencyError,
    InvalidResourceTypeError,
    ResourceNotFoundError,
)


@pytest.fixture
def registry_service(db) -> RegistryService:
    return RegistryService(db)


def test_get_pair_delegates_to_interop(monkeypatch, db):
    captured: dict[str, tuple[str, str]] = {}

    def fake_fetch_pair(gene_id: str, strain_id: str) -> dict[str, str]:
        captured["args"] = (gene_id, strain_id)
        return {"pair": f"{gene_id}:{strain_id}"}

    monkeypatch.setattr(
        "backend.interop.services.registry.InteropService.fetch_pair_attributes",
        staticmethod(fake_fetch_pair),
    )

    service = RegistryService(db)
    result = service.get_pair("gene-1", "strain-2")

    assert result == {"pair": "gene-1:strain-2"}
    assert captured["args"] == ("gene-1", "strain-2")


@pytest.mark.parametrize("gene_id,strain_id", [("", "strain-1"), ("gene-1", ""), ("", "")])
def test_get_pair_validates_identifiers(registry_service, gene_id, strain_id):
    with pytest.raises(InvalidResourceTypeError):
        registry_service.get_pair(gene_id, strain_id)


def test_get_entity_type_returns_entity(session, registry_service):
    entity = Entity(name="gene")
    session.add(entity)
    session.commit()

    result = registry_service._get_entity_type("gene")
    assert result.id == entity.id


def test_get_entity_type_raises_for_unknown(session, registry_service):
    session.add(Entity(name="strain"))
    session.commit()

    with pytest.raises(InvalidResourceTypeError):
        registry_service._get_entity_type("gene")


def _setup_mapping(session) -> tuple[Entity, SourceDb, Mapping]:
    gene_entity = Entity(name="gene")
    source_db = SourceDb(db_name="Source A")
    session.add_all([gene_entity, source_db])
    session.flush()

    mapping = Mapping(
        source_db_id=source_db.id,
        entity_type_id=gene_entity.id,
        local_id="LOC-1",
        uid="G-100",
    )
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return gene_entity, source_db, mapping


def test_resolve_mapping_by_uid(session, db):
    gene_entity, _, mapping = _setup_mapping(session)
    service = RegistryService(db)

    resolved = service._resolve_mapping("G-100", gene_entity.id, "gene")
    assert resolved.local_id == "LOC-1"


def test_resolve_mapping_by_local_id(session, db):
    gene_entity, _, mapping = _setup_mapping(session)
    service = RegistryService(db)

    resolved = service._resolve_mapping("LOC-1", gene_entity.id, "gene")
    assert resolved.uid == "G-100"


def test_resolve_mapping_raises_for_missing_uid(session, db):
    gene_entity, _, _ = _setup_mapping(session)
    service = RegistryService(db)

    with pytest.raises(ResourceNotFoundError):
        service._resolve_mapping("G-404", gene_entity.id, "gene")


def test_resolve_mapping_raises_for_missing_local_id(session, db):
    gene_entity, _, _ = _setup_mapping(session)
    service = RegistryService(db)

    with pytest.raises(ResourceNotFoundError):
        service._resolve_mapping("missing", gene_entity.id, "gene")


def test_get_registry_item_returns_enriched_payload(session, db, monkeypatch):
    gene_entity = Entity(name="gene")
    source_a = SourceDb(db_name="Source A")
    source_b = SourceDb(db_name="Source B")
    session.add_all([gene_entity, source_a, source_b])
    session.flush()

    mapping_primary = Mapping(
        source_db_id=source_a.id,
        entity_type_id=gene_entity.id,
        local_id="LOC-1",
        uid="G-100",
    )
    mapping_secondary = Mapping(
        source_db_id=source_b.id,
        entity_type_id=gene_entity.id,
        local_id="ALIAS-1",
        uid="G-200",
    )
    session.add_all([mapping_primary, mapping_secondary])
    session.add(Synonym(uid="G-100", synonym="ALIAS-1"))
    session.commit()

    calls: list[tuple[int, int, str]] = []

    def fake_fetch_attributes(source_db_id: int, entity_type_id: int, local_id: str) -> dict[str, object]:
        calls.append((source_db_id, entity_type_id, local_id))
        return {"local_id": local_id, "source_db_id": source_db_id}

    monkeypatch.setattr(
        "backend.interop.services.registry.InteropService.fetch_attributes",
        staticmethod(fake_fetch_attributes),
    )

    service = RegistryService(db)
    result = service.get_registry_item("gene", "LOC-1")

    assert result["local_id"] == "LOC-1"
    assert result["uid"] == "G-100"
    assert result["entity_type"] == "gene"
    assert len(result["attributes"]) == 2

    attributes_by_local = {item["local_id"]: item for item in result["attributes"]}

    assert attributes_by_local["LOC-1"]["source_db"] == "Source A"
    assert attributes_by_local["LOC-1"]["data"] == {"local_id": "LOC-1", "source_db_id": source_a.id}

    assert attributes_by_local["ALIAS-1"]["source_db"] == "Source B"
    assert attributes_by_local["ALIAS-1"]["data"] == {"local_id": "ALIAS-1", "source_db_id": source_b.id}

    assert set(calls) == {
        (source_a.id, gene_entity.id, "LOC-1"),
        (source_b.id, gene_entity.id, "ALIAS-1"),
    }


def test_get_registry_item_unknown_resource_type(session, db):
    session.add(Entity(name="strain"))
    session.commit()

    service = RegistryService(db)

    with pytest.raises(InvalidResourceTypeError):
        service.get_registry_item("gene", "LOC-1")


def test_get_registry_item_missing_mapping(session, db):
    gene_entity = Entity(name="gene")
    session.add(gene_entity)
    session.commit()

    service = RegistryService(db)

    with pytest.raises(ResourceNotFoundError):
        service.get_registry_item("gene", "missing")


def test_get_registry_entry_returns_row(session, db):
    gene_entity = Entity(name="gene")
    source_db = SourceDb(db_name="Source A")
    registry = Registry(source_db_id=1, entity_type_id=1, local_id="LOC-1")
    session.add_all([gene_entity, source_db])
    session.flush()
    registry.source_db_id = source_db.id
    registry.entity_type_id = gene_entity.id
    session.add(registry)
    session.commit()

    service = RegistryService(db)
    fetched = service._get_registry_entry(source_db.id, gene_entity.id, "LOC-1")

    assert fetched.source_db_id == source_db.id
    assert fetched.local_id == "LOC-1"


def test_get_registry_entry_raises_when_missing(session, db):
    gene_entity = Entity(name="gene")
    source_db = SourceDb(db_name="Source A")
    session.add_all([gene_entity, source_db])
    session.commit()

    service = RegistryService(db)

    with pytest.raises(DatabaseInconsistencyError):
        service._get_registry_entry(source_db.id, gene_entity.id, "missing")
