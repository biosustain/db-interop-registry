"""List utilities."""
import sys
import os

from utils.models import Mapping
from utils.db_connector import get_session


def list_registry():
    """List all registry entries."""
    session = get_session()
    
    try:
        mappings = session.query(Mapping).all()

        for m in mappings:
            print(f"Source DB: {m.source_db_id}, Entity Type: {m.entity_type_id}, Local ID: {m.local_id}, UID: {m.uid}")

    finally:
        session.close()