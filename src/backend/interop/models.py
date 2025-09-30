import logging
from datetime import datetime

from sqlalchemy import ForeignKey, String, func, select, DateTime
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


class Registry(db.Model):
    __tablename__ = "registry"

    source_db_id: Mapped[int] = mapped_column(ForeignKey("source_db.id", ondelete="CASCADE"), primary_key=True)
    entity_type_id: Mapped[int] = mapped_column(ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True)
    local_id: Mapped[str] = mapped_column(String(255), primary_key=True)
