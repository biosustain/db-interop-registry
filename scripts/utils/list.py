"""List utilities."""

from utils.db_connector import get_session
from utils.models import Mapping


def list_registry():
    """List all registry entries."""
    session = get_session()

    try:
        mappings = session.query(Mapping).all()

        for m in mappings:
            print(f"Source DB: {m.source_db_id}, Entity Type: {m.entity_type_id}, Local ID: {m.local_id}, UID: {m.uid}")

    finally:
        session.close()
