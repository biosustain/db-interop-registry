#!/usr/bin/env python3
"""
Cleanup script for registry data.

This script takes a JSON file with UIDs to delete, removes them from the mapping table,
and also removes the corresponding entries from the registry table.
"""

import json
import sys

from utils.db_connector import get_session
from utils.models import AuditLog, Entity, Mapping, Registry, SourceDb, Synonym


def _parse_synonym_deletions(spec) -> dict[str, set[str]]:
    """
    Parse a synonyms removal spec into {uid: {synonym,...}, ...}.

    Accepted shapes:
      - { "UID": ["syn1", "syn2"], ... }
      - [ {"uid": "UID", "synonym": "syn"}, {"uid": "UID", "synonyms": ["a","b"]}, ... ]
      - [ ["UID", "syn"], ... ]
    """
    result: dict[str, set[str]] = {}
    if spec is None:
        return result

    def add(uid_raw, syns_raw):
        if uid_raw is None:
            return
        uid = str(uid_raw).strip()
        if not uid:
            return
        if isinstance(syns_raw, (list, tuple)):
            items = syns_raw
        else:
            items = [syns_raw]
        for s in items:
            if s is None:
                continue
            syn = str(s).strip()
            if syn:
                result.setdefault(uid, set()).add(syn)

    if isinstance(spec, dict):
        for uid, values in spec.items():
            if isinstance(values, (list, tuple)):
                add(uid, list(values))
            else:
                # skip invalid shapes silently
                continue
        return result

    if isinstance(spec, list):
        for item in spec:
            if item is None:
                continue
            if isinstance(item, dict):
                uid = item.get("uid")
                if "synonym" in item:
                    add(uid, item.get("synonym"))
                if "synonyms" in item and isinstance(item.get("synonyms"), (list, tuple)):
                    add(uid, item.get("synonyms"))
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                add(item[0], item[1])
            else:
                continue
        return result

    return result


def cleanup_all_data() -> None:
    """
    Clean up ALL data from mapping and registry tables.
    WARNING: This will delete everything!
    """
    print("Starting cleanup of ALL registry and mapping data...")
    print("WARNING: This will delete EVERYTHING from mapping and registry tables!")

    confirm = input("Type 'y' to confirm complete data deletion: ").strip()
    if confirm != "y":
        print("Cleanup cancelled - confirmation text did not match")
        return

    session = get_session()

    try:
        # Count existing records for reporting
        mapping_count = session.query(Mapping).count()
        registry_count = session.query(Registry).count()
        synonym_count = session.query(Synonym).count()

        print(f"Found {mapping_count} mapping, {registry_count} registry, and {synonym_count} synonyms")

        if mapping_count == 0 and registry_count == 0 and synonym_count == 0:
            print("Database is already empty - nothing to clean up")
            return

        # Precompute audit log entries for synonyms and UIDs
        synonym_rows = session.query(Synonym.uid, Synonym.synonym).all()
        synonym_audit = [
            {"uid": (r[0] if not hasattr(r, "uid") else r.uid), "event_type": "Removed synonym " + (r[1] if not hasattr(r, "synonym") else r.synonym)}
            for r in synonym_rows
        ]

        mapping_uid_rows = session.query(Mapping.uid).all()
        # Deduplicate UIDs so we write one "Removed" per UID
        uid_values = set()
        for r in mapping_uid_rows:
            uid_values.add(r[0] if not hasattr(r, "uid") else r.uid)
        uid_audit = [{"uid": u, "event_type": "Removed"} for u in uid_values]

        # Write audit logs first (transactional with deletions)
        total_synonym_audits = len(synonym_audit)
        total_uid_audits = len(uid_audit)
        if total_synonym_audits:
            session.bulk_insert_mappings(AuditLog, synonym_audit)
        if total_uid_audits:
            session.bulk_insert_mappings(AuditLog, uid_audit)

        # Delete all synonyms
        print("Deleting all synonym entries...")
        deleted_synonyms = session.query(Synonym).delete()

        # Delete all mappings
        print("Deleting all mapping entries...")
        deleted_mappings = session.query(Mapping).delete()

        # Delete all registry entries
        print("Deleting all registry entries...")
        deleted_registry = session.query(Registry).delete()

        # Commit the changes
        session.commit()

        print("\nComplete cleanup finished!")
        print(f"   Logged {total_synonym_audits} synonym removal audit event(s)")
        print(f"   Logged {total_uid_audits} UID removal audit event(s)")
        print(f"   Deleted {deleted_synonyms} synonym entries")
        print(f"   Deleted {deleted_mappings} mapping entries")
        print(f"   Deleted {deleted_registry} registry entries")
        print("   Database is now clean and ready for fresh data")

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
        with open(file_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{file_path}': {e}")
        sys.exit(1)

    # Validate JSON structure
    uids = data.get("uids", [])
    if uids is not None and not isinstance(uids, list):
        print("Error: 'uids' must be a list if provided")
        sys.exit(1)

    synonyms_spec = data.get("synonyms")
    synonyms_to_remove = _parse_synonym_deletions(synonyms_spec)

    if not uids and not synonyms_to_remove:
        print("No UIDs or synonyms provided for cleanup")
        return

    if uids:
        print(f"🧹 Starting cleanup of {len(uids)} UIDs...")
    if synonyms_to_remove:
        pair_count = sum(len(v) for v in synonyms_to_remove.values())
        print(f"🧹 Starting synonym-only cleanup of {pair_count} pair(s) across {len(synonyms_to_remove)} UID(s)...")

    # Create database session
    session = get_session()

    try:
        successful_deletions = 0
        failed_deletions = 0
        not_found_count = 0
        total_synonyms_deleted = 0
        total_synonym_pairs = sum(len(v) for v in synonyms_to_remove.values())
        failed_synonym_batches = 0

        # Process synonym-only deletions first (if provided)
        if synonyms_to_remove:
            for i, (uid_for_syn, syn_set) in enumerate(synonyms_to_remove.items(), 1):
                try:
                    print(f"Processing synonyms {i}/{len(synonyms_to_remove)} for UID: {uid_for_syn}")
                    syn_list = sorted(syn_set)
                    if not syn_list:
                        continue
                    existing = (
                        session.query(Synonym)
                        .filter(Synonym.uid == uid_for_syn, Synonym.synonym.in_(syn_list))
                        .all()
                    )
                    for row in existing:
                        session.add(AuditLog(uid=uid_for_syn, event_type="Removed synonym " + row.synonym))
                    deleted_count = (
                        session.query(Synonym)
                        .filter(Synonym.uid == uid_for_syn, Synonym.synonym.in_(syn_list))
                        .delete(synchronize_session=False)
                    )
                    session.commit()
                    total_synonyms_deleted += deleted_count
                    print(
                        f"   UID {uid_for_syn}: removed {deleted_count} of {len(syn_list)} requested synonym(s)"
                    )
                except Exception as e:
                    print(f"   Error removing synonyms for UID '{uid_for_syn}': {e}")
                    session.rollback()
                    failed_synonym_batches += 1

        # Then process full UID deletions (if provided)
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

                # First, remove any synonyms associated with this UID
                synonym_rows = session.query(Synonym).filter(Synonym.uid == uid).all()
                removed_synonyms_count = 0
                if synonym_rows:
                    # Log each removed synonym
                    for s in synonym_rows:
                        session.add(AuditLog(uid=uid, event_type="Removed synonym " + s.synonym))
                    # Bulk delete the synonyms for efficiency
                    removed_synonyms_count = (
                        session.query(Synonym).filter(Synonym.uid == uid).delete(synchronize_session=False)
                    )
                    print(f"   Deleted {removed_synonyms_count} synonym(s)")
                    total_synonyms_deleted += removed_synonyms_count

                # Delete from mapping table next
                session.delete(mapping_entry)
                print("   Deleted from mapping table")

                # Now find and delete the corresponding registry entry
                registry_entry = (
                    session.query(Registry)
                    .filter(
                        Registry.source_db_id == source_db_id,
                        Registry.entity_type_id == entity_type_id,
                        Registry.local_id == local_id,
                    )
                    .first()
                )

                if registry_entry:
                    session.delete(registry_entry)
                    print("   Deleted from registry table")
                else:
                    print("   No corresponding registry entry found (orphaned mapping)")

                session.add(AuditLog(uid=uid, event_type="Removed"))

                # Commit this deletion
                session.commit()
                successful_deletions += 1
                print(f"   UID '{uid}' cleanup completed!")

            except Exception as e:
                print(f"   Error processing UID '{uid}': {e}")
                session.rollback()
                failed_deletions += 1
                continue

        print("\nCleanup completed!")
        print(f"   Successfully deleted: {successful_deletions}")
        print(f"   Failed deletions: {failed_deletions}")
        print(f"   UIDs not found: {not_found_count}")
        print(f"   Total processed: {len(uids)}")
        if total_synonym_pairs or total_synonyms_deleted:
            print(
                f"   Synonym pairs requested: {total_synonym_pairs}, removed: {total_synonyms_deleted}, failed batches: {failed_synonym_batches}"
            )

        if successful_deletions > 0:
            print("\n Summary of deletions:")
            print(f"   • Removed {successful_deletions} entries from mapping table")
            print(f"   • Removed {successful_deletions} entries from registry table")

    except Exception as e:
        print(f"Fatal error during cleanup: {e}")
        session.rollback()
        sys.exit(1)

    finally:
        session.close()
