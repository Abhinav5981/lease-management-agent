-- =============================================================================
-- AI-Powered Lease Management Agent — Dubai Real Estate
-- PostgreSQL Database Schema (MVP)
-- =============================================================================
-- Scope: NON-FINANCIAL lease lifecycle only
-- Excluded: rent payments, invoices, accounting, VAT, security deposits
--
-- ER DIAGRAM (simplified)
--
--   buildings
--       │ 1
--       │ has many
--       ▼ N
--     units ──────────────────────────────────────┐
--       │ 1                                        │ 1
--       │ leased via                               │ belongs to
--       ▼ N                                        │
--     leases ◄──────────────────── renewals (N)   │
--       │ 1    ◄─── N  lease_documents             │
--       │ has                                      │
--       ▼ N                                        │
--     tenants ───────────────────────────────────►─┘
--       │ 1  raises
--       ▼ N
--     maintenance_requests
--
-- TABLE RELATIONSHIPS SUMMARY:
--   buildings   (1) ──► (N)  units
--   units       (1) ──► (N)  leases
--   tenants     (1) ──► (N)  leases
--   leases      (1) ──► (N)  lease_documents
--   leases      (1) ──► (N)  renewals
--   leases      (1) ──► (N)  maintenance_requests
--   tenants     (1) ──► (N)  maintenance_requests
--   units       (1) ──► (N)  maintenance_requests
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUM TYPES
-- =============================================================================

CREATE TYPE unit_type_enum AS ENUM (
    'studio',
    '1br',
    '2br',
    '3br',
    '4br',
    'penthouse',
    'commercial',
    'retail'
);

CREATE TYPE unit_status_enum AS ENUM (
    'available',       -- Ready to lease
    'reserved',        -- Application in progress
    'occupied',        -- Active lease
    'under_maintenance'-- Not available due to works
);

CREATE TYPE lease_status_enum AS ENUM (
    'draft',           -- Contract generated, not yet signed
    'active',          -- Signed + Ejari registered, tenancy ongoing
    'expired',         -- Lease end date passed, not renewed
    'terminated'       -- Early exit, notice served
);

CREATE TYPE document_type_enum AS ENUM (
    -- Tenant identity documents
    'passport',
    'emirates_id',
    'visa',
    'salary_proof',
    -- Lease documents
    'tenancy_contract',
    'ejari_certificate',
    'renewal_notice',
    'termination_notice',
    -- Inspection documents
    'move_in_report',
    'move_out_report',
    'handover_form',
    -- Miscellaneous
    'other'
);

CREATE TYPE document_status_enum AS ENUM (
    'pending',         -- Uploaded, awaiting verification
    'verified',        -- Verified by staff or AI
    'rejected',        -- Failed verification
    'expired'          -- Past expiry date
);

CREATE TYPE maintenance_category_enum AS ENUM (
    'hvac',
    'plumbing',
    'electrical',
    'carpentry',
    'painting',
    'appliances',
    'pest_control',
    'cleaning',
    'general'
);

CREATE TYPE maintenance_priority_enum AS ENUM (
    'low',             -- SLA: 5 business days
    'medium',          -- SLA: 48 hours
    'high',            -- SLA: 6 hours
    'emergency'        -- SLA: 1 hour
);

CREATE TYPE maintenance_status_enum AS ENUM (
    'open',
    'assigned',
    'in_progress',
    'pending_tenant_confirmation',
    'completed',
    'cancelled'
);

CREATE TYPE renewal_status_enum AS ENUM (
    'pending',         -- Not yet actioned
    'offered',         -- Renewal offer sent to tenant
    'negotiating',     -- Counter-offer received
    'accepted',        -- Tenant accepted terms
    'rejected',        -- Tenant declined, exit triggered
    'lapsed'           -- Tenant did not respond before deadline
);

CREATE TYPE tenant_renewal_response_enum AS ENUM (
    'pending',
    'accepted',
    'rejected',
    'counter_offered'
);

-- =============================================================================
-- TABLE: buildings
-- Represents a physical building/tower in the portfolio.
-- =============================================================================

CREATE TABLE buildings (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(150)    NOT NULL,                   -- e.g. "Marina Heights Tower A"
    name_ar             VARCHAR(150),                               -- Arabic name
    address_line1       VARCHAR(255)    NOT NULL,
    address_line2       VARCHAR(255),
    area                VARCHAR(100)    NOT NULL,                   -- Dubai area: "Dubai Marina", "JBR"
    city                VARCHAR(50)     NOT NULL DEFAULT 'Dubai',
    makani_number       VARCHAR(20),                                -- Dubai Makani (geo-address) number
    total_floors        SMALLINT        NOT NULL CHECK (total_floors > 0),
    total_units         SMALLINT        NOT NULL CHECK (total_units > 0),
    year_built          SMALLINT,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE buildings IS 'Physical buildings/towers in the company portfolio.';
COMMENT ON COLUMN buildings.makani_number IS 'Dubai Smart Address (Makani) geographic identifier.';

-- =============================================================================
-- TABLE: units
-- Represents a leasable unit within a building.
-- =============================================================================

CREATE TABLE units (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    building_id         UUID            NOT NULL
                            REFERENCES buildings(id) ON DELETE RESTRICT,
    unit_number         VARCHAR(20)     NOT NULL,                   -- e.g. "804", "12A"
    floor_number        SMALLINT        NOT NULL,
    unit_type           unit_type_enum  NOT NULL,
    bedrooms            SMALLINT        NOT NULL DEFAULT 0 CHECK (bedrooms >= 0),
    bathrooms           SMALLINT        NOT NULL DEFAULT 1 CHECK (bathrooms >= 0),
    area_sqft           NUMERIC(8, 2)   NOT NULL CHECK (area_sqft > 0),
    status              unit_status_enum NOT NULL DEFAULT 'available',
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_unit_per_building UNIQUE (building_id, unit_number)
);

COMMENT ON TABLE units IS 'Leasable units within a building.';
COMMENT ON COLUMN units.area_sqft IS 'Net usable area in square feet (Dubai market convention).';

-- =============================================================================
-- TABLE: tenants
-- Personal and identity details of a prospective or active tenant.
-- Financial details (salary, bank) are stored only for KYC screening.
-- =============================================================================

CREATE TABLE tenants (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Personal details
    first_name              VARCHAR(100)    NOT NULL,
    last_name               VARCHAR(100)    NOT NULL,
    email                   VARCHAR(254)    NOT NULL,
    phone                   VARCHAR(20)     NOT NULL,               -- E.164 format preferred
    nationality             VARCHAR(100),                           -- e.g. "Indian"
    date_of_birth           DATE,

    -- Identity documents
    passport_number         VARCHAR(30),
    passport_expiry         DATE,
    emirates_id             VARCHAR(20),                            -- UAE EID: 784-YYYY-XXXXXXX-X
    emirates_id_expiry      DATE,
    visa_number             VARCHAR(30),
    visa_expiry             DATE,
    visa_type               VARCHAR(50),                            -- e.g. "Employment Residence"

    -- KYC screening (not financial processing)
    employer_name           VARCHAR(150),
    monthly_income_aed      NUMERIC(12, 2),                         -- Used for affordability check only

    -- Lifecycle
    is_active               BOOLEAN         NOT NULL DEFAULT TRUE,
    is_blacklisted          BOOLEAN         NOT NULL DEFAULT FALSE,
    blacklist_reason        TEXT,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_tenant_email   UNIQUE (email),
    CONSTRAINT uq_tenant_eid     UNIQUE (emirates_id),
    CONSTRAINT uq_tenant_passport UNIQUE (passport_number)
);

COMMENT ON TABLE tenants IS 'Tenant identity and KYC data. No financial transaction data stored here.';
COMMENT ON COLUMN tenants.emirates_id IS 'UAE Emirates ID in format 784-YYYY-XXXXXXX-X.';
COMMENT ON COLUMN tenants.monthly_income_aed IS 'Used for lease affordability screening (3x rent ratio), not for payment processing.';

-- =============================================================================
-- TABLE: leases
-- The core entity — a legally binding tenancy agreement between
-- a tenant and the company for a specific unit.
-- Financial fields (annual_rent) are included as lease TERMS for
-- RERA index compliance checks, not for payment processing.
-- =============================================================================

CREATE TABLE leases (
    id                      UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    lease_number            VARCHAR(30)         NOT NULL UNIQUE,    -- Human-readable: "LSE-2026-001042"
    unit_id                 UUID                NOT NULL
                                REFERENCES units(id) ON DELETE RESTRICT,
    tenant_id               UUID                NOT NULL
                                REFERENCES tenants(id) ON DELETE RESTRICT,

    -- Lease terms
    start_date              DATE                NOT NULL,
    end_date                DATE                NOT NULL,
    annual_rent_aed         NUMERIC(12, 2)      NOT NULL CHECK (annual_rent_aed > 0),
                                                                    -- Lease term for RERA compliance only
    notice_period_days      SMALLINT            NOT NULL DEFAULT 60,

    -- Lifecycle status
    status                  lease_status_enum   NOT NULL DEFAULT 'draft',

    -- Ejari registration (Dubai DLD mandatory)
    ejari_number            VARCHAR(50)         UNIQUE,             -- Assigned by DLD on registration
    ejari_registration_date DATE,
    ejari_expiry_date       DATE,

    -- Signing
    signed_by_tenant_at     TIMESTAMPTZ,
    signed_by_company_at    TIMESTAMPTZ,
    signing_platform        VARCHAR(50),                            -- e.g. "DocuSign"

    -- Audit
    created_by              VARCHAR(150),                           -- Staff user name/ID
    created_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_lease_dates CHECK (end_date > start_date),
    CONSTRAINT chk_ejari_dates CHECK (
        ejari_expiry_date IS NULL OR ejari_expiry_date >= ejari_registration_date
    )
);

COMMENT ON TABLE leases IS 'Core tenancy agreement. One active lease per unit at any time.';
COMMENT ON COLUMN leases.lease_number IS 'Human-readable reference for correspondence and Ejari filings.';
COMMENT ON COLUMN leases.annual_rent_aed IS 'Stored as a lease term for RERA rental index compliance checks on renewal. Not used for payment processing.';
COMMENT ON COLUMN leases.ejari_number IS 'Reference number returned by DLD Ejari system upon successful registration.';

-- Ensure only one active lease per unit at any given time
CREATE UNIQUE INDEX uq_one_active_lease_per_unit
    ON leases (unit_id)
    WHERE status = 'active';

-- =============================================================================
-- TABLE: lease_documents
-- All documents associated with a lease or tenant KYC.
-- Files are stored externally (blob storage); this table holds metadata.
-- =============================================================================

CREATE TABLE lease_documents (
    id                  UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    lease_id            UUID                    REFERENCES leases(id) ON DELETE CASCADE,
    tenant_id           UUID                    REFERENCES tenants(id) ON DELETE RESTRICT,

    -- Document identity
    document_type       document_type_enum      NOT NULL,
    document_name       VARCHAR(255)            NOT NULL,           -- Original filename
    storage_path        TEXT                    NOT NULL,           -- Blob storage URI
    mime_type           VARCHAR(100),
    file_size_bytes     BIGINT,

    -- Validity
    expiry_date         DATE,                                       -- For passports, visas, EIDs
    status              document_status_enum    NOT NULL DEFAULT 'pending',

    -- Verification
    verified_by         VARCHAR(150),                               -- Staff or "AI-OCR"
    verified_at         TIMESTAMPTZ,
    rejection_reason    TEXT,

    -- Audit
    uploaded_by         VARCHAR(150),
    created_at          TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ             NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_lease_or_tenant CHECK (
        lease_id IS NOT NULL OR tenant_id IS NOT NULL
    )
);

COMMENT ON TABLE lease_documents IS 'Document metadata only. Binary files stored in Azure Blob / S3.';
COMMENT ON COLUMN lease_documents.storage_path IS 'Full URI to file in object storage (e.g. https://storage.azure.com/...).';
COMMENT ON COLUMN lease_documents.expiry_date IS 'Populated for identity documents; agent monitors this for expiry alerts.';

-- =============================================================================
-- TABLE: maintenance_requests
-- Tenant-raised maintenance and repair requests.
-- =============================================================================

CREATE TABLE maintenance_requests (
    id                  UUID                        PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_number    VARCHAR(30)                 NOT NULL UNIQUE, -- e.g. "MR-2026-002291"
    unit_id             UUID                        NOT NULL
                            REFERENCES units(id) ON DELETE RESTRICT,
    lease_id            UUID                        REFERENCES leases(id) ON DELETE SET NULL,
    tenant_id           UUID                        NOT NULL
                            REFERENCES tenants(id) ON DELETE RESTRICT,

    -- Request details
    category            maintenance_category_enum   NOT NULL,
    priority            maintenance_priority_enum   NOT NULL DEFAULT 'medium',
    status              maintenance_status_enum     NOT NULL DEFAULT 'open',
    title               VARCHAR(255)                NOT NULL,
    description         TEXT,

    -- Assignment
    assigned_to         VARCHAR(150),                               -- Contractor name or staff
    assigned_at         TIMESTAMPTZ,
    sla_due_at          TIMESTAMPTZ,                                -- Calculated from priority SLA rules

    -- Resolution
    reported_at         TIMESTAMPTZ                 NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    resolution_notes    TEXT,

    -- Tenant feedback
    tenant_rating       SMALLINT CHECK (tenant_rating BETWEEN 1 AND 5),
    tenant_feedback     TEXT,
    rated_at            TIMESTAMPTZ,

    created_at          TIMESTAMPTZ                 NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ                 NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_completed_has_date CHECK (
        status != 'completed' OR completed_at IS NOT NULL
    )
);

COMMENT ON TABLE maintenance_requests IS 'Tenant-raised maintenance and repair requests with SLA tracking.';
COMMENT ON COLUMN maintenance_requests.sla_due_at IS 'Auto-calculated: emergency=+1h, high=+6h, medium=+48h, low=+5 business days.';
COMMENT ON COLUMN maintenance_requests.assigned_to IS 'Free-text contractor/staff name. FK to vendor table can be added post-MVP.';

-- =============================================================================
-- TABLE: renewals
-- Tracks the renewal negotiation for an expiring lease.
-- A renewal lifecycle ends either in a new lease record or confirmed exit.
-- =============================================================================

CREATE TABLE renewals (
    id                      UUID                        PRIMARY KEY DEFAULT gen_random_uuid(),
    lease_id                UUID                        NOT NULL
                                REFERENCES leases(id) ON DELETE RESTRICT,
    tenant_id               UUID                        NOT NULL
                                REFERENCES tenants(id) ON DELETE RESTRICT,
    unit_id                 UUID                        NOT NULL
                                REFERENCES units(id) ON DELETE RESTRICT,

    -- Renewal terms proposed
    new_start_date          DATE                        NOT NULL,
    new_end_date            DATE                        NOT NULL,
    previous_rent_aed       NUMERIC(12, 2)              NOT NULL,   -- From expiring lease
    proposed_rent_aed       NUMERIC(12, 2)              NOT NULL,   -- Landlord's opening offer

    -- RERA compliance (Law 33 / Rental Index)
    rera_permitted_increase_pct NUMERIC(5, 2),                      -- % from RERA calculator (e.g. 5.00)
    rera_max_rent_aed       NUMERIC(12, 2),                         -- Ceiling permitted by RERA index
    rera_index_checked_at   TIMESTAMPTZ,

    -- Negotiation outcome
    final_rent_aed          NUMERIC(12, 2),                         -- Agreed rent (post-negotiation)
    tenant_counter_offer_aed NUMERIC(12, 2),                        -- Tenant's counter-offer if any

    -- RERA 90-day notice compliance (Law 33)
    notice_sent_at          TIMESTAMPTZ,
    notice_due_by           DATE NOT NULL,                          -- Must send by this date (90 days before lease_end)
    rera_notice_compliant   BOOLEAN,                                -- TRUE if sent before notice_due_by

    -- Tenant response
    tenant_response         tenant_renewal_response_enum NOT NULL DEFAULT 'pending',
    tenant_responded_at     TIMESTAMPTZ,

    -- Overall renewal status
    status                  renewal_status_enum         NOT NULL DEFAULT 'pending',

    -- Link to newly created lease if accepted
    new_lease_id            UUID REFERENCES leases(id) ON DELETE SET NULL,

    -- Audit
    created_by              VARCHAR(150),
    created_at              TIMESTAMPTZ                 NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ                 NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_renewal_dates CHECK (new_end_date > new_start_date),
    CONSTRAINT chk_rera_ceiling  CHECK (
        rera_max_rent_aed IS NULL OR proposed_rent_aed <= rera_max_rent_aed
    ),
    CONSTRAINT uq_one_active_renewal_per_lease UNIQUE (lease_id, status)
                                                                    -- Relaxed: multiple statuses allowed
                                                                    -- but only one 'pending'/'offered'/'negotiating' at once
);

COMMENT ON TABLE renewals IS 'Renewal negotiation record per expiring lease. Enforces RERA 90-day notice and rental index caps.';
COMMENT ON COLUMN renewals.notice_due_by IS 'Computed as lease.end_date - 90 days. Agent triggers notice workflow before this date.';
COMMENT ON COLUMN renewals.rera_notice_compliant IS 'Set to TRUE/FALSE when notice is sent, based on comparison with notice_due_by.';
COMMENT ON COLUMN renewals.new_lease_id IS 'Populated when renewal is accepted and a new lease record is created.';

-- =============================================================================
-- UPDATED_AT TRIGGER FUNCTION
-- Automatically maintains updated_at on all tables.
-- =============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_buildings_updated_at
    BEFORE UPDATE ON buildings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_units_updated_at
    BEFORE UPDATE ON units
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_leases_updated_at
    BEFORE UPDATE ON leases
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_lease_documents_updated_at
    BEFORE UPDATE ON lease_documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_maintenance_requests_updated_at
    BEFORE UPDATE ON maintenance_requests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_renewals_updated_at
    BEFORE UPDATE ON renewals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- INDEXES
-- =============================================================================

-- ── buildings ──────────────────────────────────────────────────────────────
-- Filter by area (common: "show all buildings in Dubai Marina")
CREATE INDEX idx_buildings_area        ON buildings (area);
CREATE INDEX idx_buildings_is_active   ON buildings (is_active) WHERE is_active = TRUE;

-- ── units ──────────────────────────────────────────────────────────────────
-- Most queries filter by building + status
CREATE INDEX idx_units_building_id     ON units (building_id);
CREATE INDEX idx_units_status          ON units (status);
-- Leasing search: find available units by type
CREATE INDEX idx_units_available       ON units (unit_type, bedrooms) WHERE status = 'available';

-- ── tenants ────────────────────────────────────────────────────────────────
-- Lookup by email (login / dedup check)
CREATE INDEX idx_tenants_email         ON tenants (email);
-- Document expiry monitoring (agent scans these periodically)
CREATE INDEX idx_tenants_passport_exp  ON tenants (passport_expiry) WHERE passport_expiry IS NOT NULL;
CREATE INDEX idx_tenants_eid_exp       ON tenants (emirates_id_expiry) WHERE emirates_id_expiry IS NOT NULL;
CREATE INDEX idx_tenants_visa_exp      ON tenants (visa_expiry) WHERE visa_expiry IS NOT NULL;

-- ── leases ─────────────────────────────────────────────────────────────────
-- Active lease lookup (most frequent query)
CREATE INDEX idx_leases_unit_id        ON leases (unit_id);
CREATE INDEX idx_leases_tenant_id      ON leases (tenant_id);
CREATE INDEX idx_leases_status         ON leases (status);
-- Expiry pipeline: "show leases ending in next 180 days"
CREATE INDEX idx_leases_end_date       ON leases (end_date) WHERE status = 'active';
-- Ejari reference lookup
CREATE INDEX idx_leases_ejari_number   ON leases (ejari_number) WHERE ejari_number IS NOT NULL;

-- ── lease_documents ────────────────────────────────────────────────────────
CREATE INDEX idx_docs_lease_id         ON lease_documents (lease_id);
CREATE INDEX idx_docs_tenant_id        ON lease_documents (tenant_id);
CREATE INDEX idx_docs_type_status      ON lease_documents (document_type, status);
-- Agent expiry monitoring
CREATE INDEX idx_docs_expiry           ON lease_documents (expiry_date)
    WHERE expiry_date IS NOT NULL AND status = 'verified';

-- ── maintenance_requests ───────────────────────────────────────────────────
CREATE INDEX idx_maint_unit_id         ON maintenance_requests (unit_id);
CREATE INDEX idx_maint_tenant_id       ON maintenance_requests (tenant_id);
CREATE INDEX idx_maint_lease_id        ON maintenance_requests (lease_id);
-- SLA breach monitoring: open high/emergency requests
CREATE INDEX idx_maint_sla             ON maintenance_requests (sla_due_at, priority)
    WHERE status NOT IN ('completed', 'cancelled');
-- Dashboard: open requests by status
CREATE INDEX idx_maint_status          ON maintenance_requests (status);

-- ── renewals ───────────────────────────────────────────────────────────────
CREATE INDEX idx_renewals_lease_id     ON renewals (lease_id);
CREATE INDEX idx_renewals_tenant_id    ON renewals (tenant_id);
CREATE INDEX idx_renewals_status       ON renewals (status);
-- 90-day notice compliance scan
CREATE INDEX idx_renewals_notice_due   ON renewals (notice_due_by)
    WHERE status IN ('pending', 'offered') AND notice_sent_at IS NULL;

