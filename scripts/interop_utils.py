#!/usr/bin/env python3
"""
Interop Utilities - Database Entity Management Tool
"""

import argparse
import logging
import sys
from pathlib import Path

from utils.cleanup import cleanup_all_data, cleanup_entities
from utils.ingest import ingest_entities
from utils.ingest_bulk import ingest_bulk_entities
from utils.list import list_registry
from utils.db_connector import get_session
from utils.models import BaseModel, Entity, SourceDb

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def ingest(file_path: Path) -> None:
    """Ingest entities from JSON file."""
    logger.info(f"Ingesting from {file_path}")
    ingest_entities(file_path)
    pass


def ingest_bulk() -> None:
    """Ingest entities from internal databases."""
    ingest_bulk_entities()
    pass


def update(file_path: Path) -> None:
    """Update entities from JSON file."""
    pass


def cleanup(file_path: Path = None) -> None:
    """Cleanup entities."""
    if file_path:
        logger.info(f"Cleaning up specific entities from {file_path}")
        cleanup_entities(file_path)
    else:
        logger.info("Cleaning up all entities")
        cleanup_all_data()


def list_all() -> None:
    """List all entities."""
    logger.info("Listing all entities")
    list_registry()
    pass


def init_db() -> None:
    """Initialize database schema and seed lookup tables."""
    session = get_session()
    engine = session.get_bind()

    # Create tables if they don't exist
    BaseModel.metadata.create_all(bind=engine)

    # Seed entities (idempotent)
    required_entities = ["gene", "strain"]
    for name in required_entities:
        if not session.query(Entity).filter(Entity.name == name).first():
            session.add(Entity(name=name))

    # Seed common source DBs (idempotent)
    required_sources = ["Bigg", "ALEdb", "PMKbase", "Pankb"]
    for db_name in required_sources:
        if not session.query(SourceDb).filter(SourceDb.db_name == db_name).first():
            session.add(SourceDb(db_name=db_name))

    session.commit()
    logger.info("Initialized DB schema and seeded lookup tables")


def main():
    parser = argparse.ArgumentParser(description="Interop database utilities")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ingest", type=Path, help="Ingest entities from JSON file")
    group.add_argument("--update", type=Path, help="Update entities from JSON file")
    group.add_argument("--cleanup", type=Path, help="Cleanup entities from file")
    group.add_argument("--cleanup-all", action="store_true", help="Cleanup all entities")
    group.add_argument("--list", action="store_true", help="List all entities")
    group.add_argument("--ingest-bulk", action="store_true", help="Ingest entities from internal databases")
    group.add_argument("--init-db", action="store_true", help="Create tables and seed lookup data")

    args = parser.parse_args()

    if args.ingest_bulk:
        ingest_bulk()
    if args.ingest:
        ingest(args.ingest)
    elif args.update:
        update(args.update)
    elif args.cleanup:
        cleanup(args.cleanup)
    elif args.cleanup_all:
        cleanup()
    elif args.list:
        list_all()
    elif args.init_db:
        init_db()

    return 0


if __name__ == "__main__":
    sys.exit(main())
