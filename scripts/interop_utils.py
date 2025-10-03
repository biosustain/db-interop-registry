#!/usr/bin/env python3
"""
Interop Utilities - Database Entity Management Tool
"""

import sys
import argparse
import logging
from pathlib import Path
from utils.list import list_registry
from utils.ingest import ingest_entities
from utils.ingest_bulk import ingest_bulk_entities
from utils.cleanup import cleanup_all_data, cleanup_entities

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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


def main():
    parser = argparse.ArgumentParser(description='Interop database utilities')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--ingest', type=Path, help='Ingest entities from JSON file')
    group.add_argument('--update', type=Path, help='Update entities from JSON file')
    group.add_argument('--cleanup', type=Path, help='Cleanup entities from file')
    group.add_argument('--cleanup-all', action='store_true', help='Cleanup all entities')
    group.add_argument('--list', action='store_true', help='List all entities')
    group.add_argument('--ingest-bulk', action='store_true', help='Ingest entities from internal databases')
    
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
    
    return 0


if __name__ == '__main__':
    sys.exit(main())