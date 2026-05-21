import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ServiceORM(Base):
    __tablename__ = "services"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    team: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class DeploymentORM(Base):
    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name: Mapped[str] = mapped_column(
        String(100), ForeignKey("services.name"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    deployer: Mapped[str] = mapped_column(String(100), nullable=False)
    commit_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'success'"))
    failure_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        # Composite index for efficient service-based time-range queries
        Index("ix_deployments_service_deployed_at", "service_name", "deployed_at"),
        # Partial index for failure/recovery lookups
        Index(
            "ix_deployments_failed_status",
            "status",
            postgresql_where=text("status IN ('failed', 'recovered')"),
        ),
    )
