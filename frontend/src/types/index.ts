// ── Enums ─────────────────────────────────────────────────────────────────

export type LeaseStatus = "draft" | "active" | "expired" | "terminated";
export type UnitStatus = "available" | "reserved" | "occupied" | "under_maintenance";
export type UnitType = "studio" | "1br" | "2br" | "3br" | "4br" | "penthouse" | "commercial" | "retail";
export type MaintenancePriority = "emergency" | "high" | "medium" | "low";
export type MaintenanceStatus =
  | "open"
  | "assigned"
  | "in_progress"
  | "pending_tenant_confirmation"
  | "completed"
  | "cancelled";
export type RenewalStatus = "pending" | "offered" | "accepted" | "rejected" | "lapsed";

// ── Core entities ─────────────────────────────────────────────────────────

export interface Building {
  id: string;
  name: string;
  area: string;
  address: string;
  total_floors: number;
  total_units: number;
  is_active: boolean;
}

export interface Unit {
  id: string;
  unit_number: string;
  floor_number: number;
  unit_type: UnitType;
  bedrooms: number;
  bathrooms: number;
  area_sqft: number;
  status: UnitStatus;
  building_id: string;
  building?: Building;
}

export interface Tenant {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  nationality: string;
  emirates_id: string | null;
  passport_expiry: string | null;
  visa_expiry: string | null;
  is_blacklisted: boolean;
  is_active: boolean;
}

export interface Lease {
  id: string;
  lease_number: string;
  status: LeaseStatus;
  start_date: string;
  end_date: string;
  annual_rent_aed: number;
  notice_period_days: number;
  ejari_number: string | null;
  signed_by_tenant_at: string | null;
  signed_by_company_at: string | null;
  created_at: string;
  tenant?: Tenant;
  unit?: Unit & { building?: Building };
}

export interface MaintenanceRequest {
  id: string;
  reference_number: string;
  category: string;
  priority: MaintenancePriority;
  status: MaintenanceStatus;
  title: string;
  description: string | null;
  sla_due_at: string | null;
  reported_at: string;
  completed_at: string | null;
  tenant_rating: number | null;
  assigned_to: string | null;
  unit?: Unit & { building?: Building };
  tenant?: Tenant;
}

// ── Dashboard stats ────────────────────────────────────────────────────────

export interface DashboardStats {
  totalUnits: number;
  availableUnits: number;
  activeLeases: number;
  openMaintenance: number;
  expiringIn90Days: number;
}

// ── Chat ──────────────────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
}
