#!/usr/bin/env python3
"""
Cleanup script for registry data.

This script takes a JSON file with UIDs to delete, removes them from the mapping table,
and also removes the corresponding entries from the registry table.
"""

import datetime
import sys
import os
import json
import hashlib
from pathlib import Path
from utils.models import Mapping, SourceDb, Entity, Registry
from utils.db_connector import get_session


def cleanup_all_data() -> None:
    """
    Clean up ALL data from mapping and registry tables.
    WARNING: This will delete everything!
    """
    print("Starting cleanup of ALL registry and mapping data...")
    print("WARNING: This will delete EVERYTHING from mapping and registry tables!")

    confirm = input("Type 'y' to confirm complete data deletion: ").strip()
    if confirm != 'y':
        print("Cleanup cancelled - confirmation text did not match")
        return
    
    session = get_session()
    
    try:
        # Count existing records for reporting
        mapping_count = session.query(Mapping).count()
        registry_count = session.query(Registry).count()
        
        print(f"Found {mapping_count} mapping entries and {registry_count} registry entries")
        
        if mapping_count == 0 and registry_count == 0:
            print("Database is already empty - nothing to clean up")
            return
        
        # Delete all mappings first (due to foreign key constraints)
        print("Deleting all mapping entries...")
        deleted_mappings = session.query(Mapping).delete()
        
        # Delete all registry entries
        print("Deleting all registry entries...")
        deleted_registry = session.query(Registry).delete()
        
        # Commit the changes
        session.commit()
        
        print(f"\nComplete cleanup finished!")
        print(f"   Deleted {deleted_mappings} mapping entries")
        print(f"   Deleted {deleted_registry} registry entries")
        print(f"   Database is now clean and ready for fresh data")
        
    except Exception as e:
        print(f"Fatal error during complete cleanup: {e}")
        session.rollback()
        sys.exit(1)
    
    finally:
        session.close()
  
        
def cleanup_entities(file_path: str) -> None:
    """
    Clean up (delete) entities and their corresponding registry entries.

    Args:
        file_path: Path to the JSON file containing entities to delete
    """
    # Load JSON data
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{file_path}': {e}")
        sys.exit(1)
    
    # Validate JSON structure
    if "uids" not in data:
        print("Error: JSON file must contain 'uids' key")
        sys.exit(1)
    
    uids = data["uids"]
    if not isinstance(uids, list):
        print("Error: 'uids' must be a list")
        sys.exit(1)
    
    if not uids:
        print("No UIDs provided for cleanup")
        return
    
    print(f"🧹 Starting cleanup of {len(uids)} UIDs...")
    
    # Create database session
    session = get_session()
    
    try:
        successful_deletions = 0
        failed_deletions = 0
        not_found_count = 0
        
        for i, uid in enumerate(uids, 1):
            try:
                print(f"Processing UID {i}/{len(uids)}: {uid}")
                
                # Find the mapping entry by UID
                mapping_entry = session.query(Mapping).filter(Mapping.uid == uid).first()
                
                if not mapping_entry:
                    print(f"   UID '{uid}' not found in mapping table")
                    not_found_count += 1
                    continue
                
                # Get the registry key information from the mapping
                source_db_id = mapping_entry.source_db_id
                entity_type_id = mapping_entry.entity_type_id
                local_id = mapping_entry.local_id
                
                # Get source_db and entity_type names for logging
                source_db = session.query(SourceDb).filter(SourceDb.id == source_db_id).first()
                entity_type = session.query(Entity).filter(Entity.id == entity_type_id).first()

                source_db_name = source_db.db_name if source_db else f"ID:{source_db_id}"
                entity_type_name = entity_type.name if entity_type else f"ID:{entity_type_id}"
                
                print(f"   Found mapping: {source_db_name} | {entity_type_name} | {local_id}")
                
                # Delete from mapping table first
                session.delete(mapping_entry)
                print(f"   Deleted from mapping table")
                
                # Now find and delete the corresponding registry entry
                registry_entry = session.query(Registry).filter(
                    Registry.source_db_id == source_db_id,
                    Registry.entity_type_id == entity_type_id,
                    Registry.local_id == local_id
                ).first()
                
                if registry_entry:
                    session.delete(registry_entry)
                    print(f"   Deleted from registry table")
                else:
                    print(f"   No corresponding registry entry found (orphaned mapping)")
                
                # Commit this deletion
                session.commit()
                successful_deletions += 1
                print(f"   UID '{uid}' cleanup completed!")
                
            except Exception as e:
                print(f"   Error processing UID '{uid}': {e}")
                session.rollback()
                failed_deletions += 1
                continue
        
        print(f"\nCleanup completed!")
        print(f"   Successfully deleted: {successful_deletions}")
        print(f"   Failed deletions: {failed_deletions}")
        print(f"   UIDs not found: {not_found_count}")
        print(f"   Total processed: {len(uids)}")
        
        if successful_deletions > 0:
            print(f"\n Summary of deletions:")
            print(f"   • Removed {successful_deletions} entries from mapping table")
            print(f"   • Removed {successful_deletions} entries from registry table")
        
    except Exception as e:
        print(f"Fatal error during cleanup: {e}")
        session.rollback()
        sys.exit(1)
    
    finally:
        session.close()
