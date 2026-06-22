"""
app/models/lease_document.py
-----------------------------
Document metadata for files attached to a lease or a tenant's KYC record.

Design notes
────────────
• Binary files are stored externally (Azure Blob / S3). This table holds
  metadata only — path, type, status, expiry, and verification trail.
• A document may belong to a lease (tenancy_contract, ejari_certificate…)
  OR to a tenant directly (passport, visa, EID) without a lease yet.
  The CHECK constraint enforces that at least one FK is set.
• expiry_date is populated for identity documents; the agent monitors this
  column via idx_docs_expiry to send renewal reminders.
• The document_status_enum and document_type_enum must already exist in
  PostgreSQL (created by schema.sql) — create_type=False prevents
  SQLAlchemy from attempting to re-create them.
"""

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.lease import Lease
    from app.models.tenant import Tenant


# ── Enums ──────────────────────────────────────────────────────────────────

class DocumentType(str, enum.Enum):
    # Tenant identity documents
    PASSPORT = "passport"
    EMIRATES_ID = "emirates_id"
    VISA = "visa"
    SALARY_PROOF = "salary_proof"
    # Lease documents
    TENANCY_CONTRACT = "tenancy_contract"
    EJARI_CERTIFICATE = "ejari_certificate"
    RENEWAL_NOTICE = "renewal_notice"
    TERMINATION_NOTICE = "termination_notice"
    # Inspection documents
    MOVE_IN_REPORT = "move_in_report"
    MOVE_OUT_REPORT = "move_out_report"
    HANDOVER_FORM = "handover_form"
    # Miscellaneous
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"      # Uploaded, awaiting AI/staff verification
    VERIFIED = "verified"    # Confirmed valid
    REJECTED = "rejected"    # Failed verification — tenant must re-upload
    EXPIRED = "expired"      # Past expiry_date; agent flags this automatically


# ── Model ──────────────────────────────────────────────────────────────────

class LeaseDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Metadata record for a document attached to a lease or a tenant KYC file.

    Relationships
    ─────────────
    lease   (N:1) — for tenancy contracts, Ejari certs, inspection reports
    tenant  (N:1) — for passport, visa, EID (may exist before a lease)
    """
    __tablename__ = "lease_documents"
    __table_args__ = (
        # At least one of lease_id or tenant_id must be set
        CheckConstraint(
            "lease_id IS NOT NULL OR tenant_id IS NOT NULL",
            name="chk_doc_lease_or_tenant",
        ),

        # FK joins
        Index("idx_docs_lease_id", "lease_id"),
        Index("idx_docs_tenant_id", "tenant_id"),

        # Agent document verification queue: filter by type + status
        Index("idx_docs_type_status", "document_type", "status"),

        # Expiry monitoring: partial — only verified docs with an expiry date need scanning
        Index(
            "idx_docs_expiry_verified",
            "expiry_date",
            postgresql_where=("expiry_date IS NOT NULL AND status = 'verified'"),
        ),
    )

    # ── Foreign keys ───────────────────────────────────────────────────
    lease_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leases.id", ondelete="CASCADE"),
        nullable=True,
        comment="Set for lease-level documents (contract, Ejari, inspection reports).",
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=True,
        comment="Set for tenant KYC documents (passport, EID, visa).",
    )

    # ── Document identity ──────────────────────────────────────────────
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type_enum", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        comment="Classifies the document for routing and display.",
    )
    document_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original filename as uploaded by the user.",
    )
    storage_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full URI to file in object storage (Azure Blob / S3). Never expose directly; generate SAS/presigned URLs.",
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        comment="MIME type, e.g. 'application/pdf', 'image/jpeg'.",
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        comment="File size in bytes for storage quota tracking.",
    )

    # ── Document validity ──────────────────────────────────────────────
    expiry_date: Mapped[date | None] = mapped_column(
        Date,
        comment="Populated for identity documents (passport, EID, visa). Agent monitors this.",
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status_enum", create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=DocumentStatus.PENDING,
    )

    # ── Verification trail ─────────────────────────────────────────────
    verified_by: Mapped[str | None] = mapped_column(
        String(150),
        comment="Staff username or 'AI-OCR' when auto-verified.",
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        comment="Reason shown to tenant when status = rejected.",
    )

    # ── Audit ──────────────────────────────────────────────────────────
    uploaded_by: Mapped[str | None] = mapped_column(
        String(150),
        comment="Username or 'tenant-portal' / 'staff-portal' identifier.",
    )

    # ── Relationships ──────────────────────────────────────────────────
    lease: Mapped["Lease | None"] = relationship(
        "Lease",
        back_populates="documents",
        foreign_keys=[lease_id],
    )
    tenant: Mapped["Tenant | None"] = relationship(
        "Tenant",
        back_populates="documents",
        foreign_keys=[tenant_id],
    )
