from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend import db


class Entity(db.Model):
    __tablename__ = "entity"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))


class SourceDb(db.Model):
    __tablename__ = "source_db"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    db_name: Mapped[str] = mapped_column(String(255))


class Mapping(db.Model):
    __tablename__ = "mapping"

    source_db_id: Mapped[int] = mapped_column(ForeignKey("source_db.id", ondelete="CASCADE"), primary_key=True)
    entity_type_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True)
    local_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    uid: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class Synonym(db.Model):
    __tablename__ = "synonyms"

    uid: Mapped[str] = mapped_column(String(255), primary_key=True)
    synonym: Mapped[str] = mapped_column(String(255), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), server_default=func.now(), onupdate=func.now())


class Registry(db.Model):
    __tablename__ = "registry"

    source_db_id: Mapped[int] = mapped_column(ForeignKey("source_db.id", ondelete="CASCADE"), primary_key=True)
    entity_type_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True)
    local_id: Mapped[str] = mapped_column(String(255), primary_key=True)


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now())
    uid: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(255))


class GeneStrainRelationship(db.Model):
    """
    Tracks the relationship between genes and strains.
    Records which genes exist in which strains, as reported by source databases.
    Uses composite primary key: (gene_uid, strain_uid, source_db_id)
    """
    __tablename__ = "gene_strain_relationship"

    gene_uid: Mapped[str] = mapped_column(String(255), primary_key=True)
    strain_uid: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_db_id: Mapped[int] = mapped_column(ForeignKey("source_db.id", ondelete="CASCADE"), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())


class EntityUrl(db.Model):
    """
    Stores URLs for entities (genes/strains) as provided by source databases.
    Uses composite primary key: (local_id, source_db_id, url_type, url)
    Multiple URLs allowed per entity (e.g., same gene in different species).
    """
    __tablename__ = "entity_url"

    local_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_db_id: Mapped[int] = mapped_column(ForeignKey("source_db.id", ondelete="CASCADE"), primary_key=True)
    url_type: Mapped[str] = mapped_column(String(50), primary_key=True)  # "gene" or "strain"
    url: Mapped[str] = mapped_column(String(1024), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())


class RelationshipUrl(db.Model):
    """
    Stores URLs for gene-strain relationships (e.g., gene-in-strain pages).
    Uses composite primary key: (gene_uid, strain_uid, source_db_id, url)
    Multiple URLs allowed per relationship (e.g., different locus_tags).
    """
    __tablename__ = "relationship_url"

    gene_uid: Mapped[str] = mapped_column(String(255), primary_key=True)
    strain_uid: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_db_id: Mapped[int] = mapped_column(ForeignKey("source_db.id", ondelete="CASCADE"), primary_key=True)
    url: Mapped[str] = mapped_column(String(1024), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), onupdate=func.now())
