from backend.interop.models import Entity, Mapping, Registry, SourceDb
from backend.interop.services.interop import InteropService
from backend.interop.utils.exceptions import DatabaseInconsistencyError, InvalidResourceTypeError, ResourceNotFoundError


class RegistryService:
    """Service for registry operations."""

    def __init__(self, db: any):
        self.db = db
        self.interop_service = InteropService()

    def get_registry_item(self, resource: str, local_id_or_uid: str) -> dict:
        """
        Retrieve registry item by resource type and identifier.

        Args:
            resource: Resource type (gene or strain)
            local_id_or_uid: Local ID or UID

        Returns:
            Registry item with mapping details

        Raises:
            InvalidResourceTypeError: If resource type is invalid
            ResourceNotFoundError: If item not found
            DatabaseInconsistencyError: If data inconsistency detected
        """
        # Resolve entity type
        entity_type = self._get_entity_type(resource)
        entity_type_id = entity_type.id

        # Resolve mapping
        mapping_entry = self._resolve_mapping(local_id_or_uid, entity_type_id, resource)
        local_id = mapping_entry.local_id

        # Get all rows from Mapping with mapping_entry.uid
        all_mappings = self.db.session.query(Mapping).filter(Mapping.uid == mapping_entry.uid).all()

        attribute_list = []
        for entity in all_mappings:
            source_db = self.db.session.query(SourceDb).filter(SourceDb.id == entity.source_db_id).first()

            attributes = self.interop_service.fetch_attributes(
                source_db_id=entity.source_db_id, entity_type_id=entity.entity_type_id, local_id=entity.local_id
            )

            attribute_list.append(
                {
                    "source_db": source_db.db_name if source_db else f"ID:{entity.source_db_id}",
                    "local_id": entity.local_id,
                    "data": attributes,
                }
            )

        return {
            "local_id": local_id,
            "uid": mapping_entry.uid,
            "entity_type": resource,
            "attributes": attribute_list,
        }

    def get_pair(self, gene_id: str, strain_id: str) -> dict:
        """Retrieve pair-based interop data directly from external services."""
        if not gene_id or not strain_id:
            raise InvalidResourceTypeError("Pair requests must include both gene and strain identifiers")

        return self.interop_service.fetch_pair_attributes(gene_id=gene_id, strain_id=strain_id)

    def _get_entity_type(self, resource: str) -> Entity:
        """Get entity type from database."""
        entity_type = self.db.session.query(Entity).filter(Entity.name == resource).first()

        if not entity_type:
            raise InvalidResourceTypeError(f"Invalid resource type: {resource}")

        return entity_type

    def _resolve_mapping(self, identifier: str, entity_type_id: int, resource: str) -> Mapping:
        """Resolve mapping by UID or local ID."""
        if identifier.startswith(("G-", "S-")):
            # Search by UID
            mapping_entry = (
                self.db.session.query(Mapping)
                .filter(Mapping.uid == identifier, Mapping.entity_type_id == entity_type_id)
                .first()
            )

            if not mapping_entry:
                raise ResourceNotFoundError(f"UID '{identifier}' not found for {resource}")
        else:
            # Search by local ID
            mapping_entry = (
                self.db.session.query(Mapping)
                .filter(Mapping.local_id == identifier, Mapping.entity_type_id == entity_type_id)
                .first()
            )

            if not mapping_entry:
                raise ResourceNotFoundError(f"Local ID '{identifier}' not found for {resource}")

        return mapping_entry

    def _get_registry_entry(self, source_db_id: int, entity_type_id: int, local_id: str) -> Registry:
        """Get registry entry and verify consistency."""
        registry_entry = (
            self.db.session.query(Registry)
            .filter(
                Registry.source_db_id == source_db_id,
                Registry.entity_type_id == entity_type_id,
                Registry.local_id == local_id,
            )
            .first()
        )

        if not registry_entry:
            raise DatabaseInconsistencyError(
                "Database inconsistency: mapping exists but no corresponding registry entry"
            )

        return registry_entry
