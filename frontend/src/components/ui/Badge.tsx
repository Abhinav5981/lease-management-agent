import type { LeaseStatus, MaintenancePriority, MaintenanceStatus, UnitStatus } from "@/types";

type Variant = "green" | "blue" | "yellow" | "red" | "gray" | "orange";

const VARIANT_CLASSES: Record<Variant, string> = {
  green:  "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  blue:   "bg-blue-50 text-blue-700 ring-blue-600/20",
  yellow: "bg-yellow-50 text-yellow-700 ring-yellow-600/20",
  red:    "bg-red-50 text-red-700 ring-red-600/20",
  gray:   "bg-slate-100 text-slate-600 ring-slate-500/20",
  orange: "bg-orange-50 text-orange-700 ring-orange-600/20",
};

interface BadgeProps {
  label: string;
  variant: Variant;
}

export function Badge({ label, variant }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${VARIANT_CLASSES[variant]}`}>
      {label}
    </span>
  );
}

// ── Typed helpers ─────────────────────────────────────────────────────────

export function LeaseStatusBadge({ status }: { status: LeaseStatus }) {
  const map: Record<LeaseStatus, { label: string; variant: Variant }> = {
    active:     { label: "Active",     variant: "green" },
    draft:      { label: "Draft",      variant: "blue" },
    expired:    { label: "Expired",    variant: "gray" },
    terminated: { label: "Terminated", variant: "red" },
  };
  const { label, variant } = map[status] ?? { label: status, variant: "gray" };
  return <Badge label={label} variant={variant} />;
}

export function UnitStatusBadge({ status }: { status: UnitStatus }) {
  const map: Record<UnitStatus, { label: string; variant: Variant }> = {
    available:         { label: "Available",    variant: "green" },
    reserved:          { label: "Reserved",     variant: "blue" },
    occupied:          { label: "Occupied",     variant: "yellow" },
    under_maintenance: { label: "Maintenance",  variant: "orange" },
  };
  const { label, variant } = map[status] ?? { label: status, variant: "gray" };
  return <Badge label={label} variant={variant} />;
}

export function PriorityBadge({ priority }: { priority: MaintenancePriority }) {
  const map: Record<MaintenancePriority, { label: string; variant: Variant }> = {
    emergency: { label: "Emergency", variant: "red" },
    high:      { label: "High",      variant: "orange" },
    medium:    { label: "Medium",    variant: "yellow" },
    low:       { label: "Low",       variant: "gray" },
  };
  const { label, variant } = map[priority] ?? { label: priority, variant: "gray" };
  return <Badge label={label} variant={variant} />;
}

export function MaintenanceStatusBadge({ status }: { status: MaintenanceStatus }) {
  const map: Record<MaintenanceStatus, { label: string; variant: Variant }> = {
    open:                        { label: "Open",         variant: "blue" },
    assigned:                    { label: "Assigned",     variant: "yellow" },
    in_progress:                 { label: "In Progress",  variant: "orange" },
    pending_tenant_confirmation: { label: "Pending",      variant: "yellow" },
    completed:                   { label: "Completed",    variant: "green" },
    cancelled:                   { label: "Cancelled",    variant: "gray" },
  };
  const { label, variant } = map[status] ?? { label: status, variant: "gray" };
  return <Badge label={label} variant={variant} />;
}
