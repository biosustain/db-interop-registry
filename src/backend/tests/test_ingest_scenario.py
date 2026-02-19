import json
import os
import socket
import sys
import types
from contextlib import closing
from pathlib import Path

import pytest
from dotenv import dotenv_values

from backend.interop.models import AuditLog, Entity, Mapping, SourceDb, Synonym, Registry


@pytest.mark.integration
def test_ingest_example_file_populates_db(db):
    # Make `scripts/utils` importable as `utils`
    repo_root = Path(__file__).resolve().parents[3]
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    # Fast connectivity check to avoid hanging when DB is down
    cfg = dotenv_values(str(scripts_dir / ".env"))
    host = cfg.get("LOCAL_DB_HOST", "localhost")
    port = int(cfg.get("LOCAL_DB_PORT", cfg.get("DBPORT", "5432")))
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(3)
        try:
            sock.connect((host, port))
        except OSError:
            pytest.skip(f"Local DB {host}:{port} not reachable; skipping ingest scenario")

    # Stub Azure imports before importing utils.db_connector (indirectly via utils.ingest)
    if "azure" not in sys.modules:
        azure_mod = types.ModuleType("azure")
        sys.modules["azure"] = azure_mod
    if "azure.identity" not in sys.modules:
        ident_mod = types.ModuleType("azure.identity")
        ident_mod.DefaultAzureCredential = object  # type: ignore[attr-defined]
        sys.modules["azure.identity"] = ident_mod
    if "azure.keyvault" not in sys.modules:
        sys.modules["azure.keyvault"] = types.ModuleType("azure.keyvault")
    if "azure.keyvault.secrets" not in sys.modules:
        secrets_mod = types.ModuleType("azure.keyvault.secrets")
        secrets_mod.SecretClient = object  # type: ignore[attr-defined]
        sys.modules["azure.keyvault.secrets"] = secrets_mod

    # Use get_local_session() so we exercise the scripts connector path
    from utils.db_connector import get_local_session  # type: ignore
    script_session = get_local_session()

    # Seed required lookup tables used by ingest in the scripts session
    gene_entity = Entity(name="gene")
    strain_entity = Entity(name="strain")
    source_aledb = SourceDb(db_name="ALEdb")
    source_pankb = SourceDb(db_name="PanKB")
    source_pmk = SourceDb(db_name="PMKbase")
    source_bigg = SourceDb(db_name="BiGGr")
    script_session.add_all([gene_entity, strain_entity, source_aledb, source_pankb, source_pmk, source_bigg])
    script_session.flush()

    # Import ingest and patch network-dependent lookups
    from utils import ingest as ingest_mod  # type: ignore

    # Ensure external fetchers return nothing during tests (no network)
    ingest_mod.fetch_ncbi_gene_synonyms = lambda gene_id, strain_id: tuple()
    ingest_mod.fetch_uniprot_id = lambda gene_id, strain_id: tuple()
    ingest_mod.fetch_ncbi_assemblies = lambda local_id: tuple()

    # Load example ingest payload
    with open(scripts_dir / "examples" / "example_ingest.json", "r") as f:
        payload = json.load(f)

    entities = payload["entities"]

    # Run ingest using the scripts local session
    ingest_mod.start_ingest(script_session, entities, chunk_size=100)
    script_session.commit()

    # Validate that rpoB mapping and synonyms were inserted
    gene_id = gene_entity.id
    aledb_id = source_aledb.id
    mapping = (
        script_session.query(Mapping)
        .filter(
            Mapping.source_db_id == aledb_id,
            Mapping.entity_type_id == gene_id,
            Mapping.local_id == "rpoB",
        )
        .first()
    )
    assert mapping is not None, "Expected mapping for ALEdb/gene/rpoB"
    uid = mapping.uid

    # Synonyms must include both values from the example file
    syns = {row.synonym for row in script_session.query(Synonym).filter(Synonym.uid == uid).all()}
    assert {"rpoB_9", "rpoB_4"}.issubset(syns)

    # Audit should include an Ingest and entries for added synonyms
    events = [row.event_type for row in script_session.query(AuditLog).filter(AuditLog.uid == uid).all()]
    
    # Clean up inserted data to avoid affecting other tests
    script_session.query(Synonym).delete(synchronize_session=False)
    script_session.query(AuditLog).delete(synchronize_session=False)
    script_session.query(Mapping).delete(synchronize_session=False)
    script_session.query(Registry).delete(synchronize_session=False)
    script_session.query(SourceDb).delete(synchronize_session=False)
    script_session.query(Entity).delete(synchronize_session=False)
    script_session.commit()
    script_session.close()
    assert "Ingest" in events
    assert "Added synonym rpoB_9" in events
    assert "Added synonym rpoB_4" in events
