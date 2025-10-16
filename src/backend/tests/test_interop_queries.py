from backend.interop.models import Entity, Mapping, SourceDb


def test_get_registry_item_returns_registry_payload(client, session, monkeypatch):
    gene_entity = Entity(name="gene")
    source_db = SourceDb(db_name="Test Source")
    session.add_all([gene_entity, source_db])
    session.flush()

    mapping = Mapping(
        source_db_id=source_db.id,
        entity_type_id=gene_entity.id,
        local_id="rpoBC",
        uid="G-123456",
    )
    session.add(mapping)
    session.commit()

    monkeypatch.setattr(
        "backend.interop.services.registry.InteropService.fetch_attributes",
        staticmethod(lambda source_db_id, entity_type_id, local_id: {"local_id": local_id}),
    )

    response = client.get("/gene/rpoBC")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["local_id"] == "rpoBC"
    assert payload["uid"] == "G-123456"
    assert payload["entity_type"] == "gene"
    assert payload["attributes"][0]["source_db"] == "Test Source"
    assert payload["attributes"][0]["local_id"] == "rpoBC"
    assert payload["attributes"][0]["data"] == {"local_id": "rpoBC"}
