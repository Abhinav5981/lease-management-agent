"use client";

import { useEffect, useState } from "react";
import { FileText, AlertTriangle, Building2, Wrench } from "lucide-react";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Stats {
  activeLeases: number;
  expiringLeases: number;
  availableUnits: number;
  openMaintenance: number;
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

interface CardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;        // Tailwind text colour for the icon background tint
  bg: string;           // Tailwind bg colour for the icon circle
}

function StatCard({ label, value, icon, color, bg }: CardProps) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 flex items-center gap-5 shadow-sm">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${bg}`}>
        <span className={color}>{icon}</span>
      </div>
      <div>
        <p className="text-sm text-gray-500 font-medium">{label}</p>
        <p className="text-3xl font-bold text-gray-900 mt-0.5 leading-none">{value}</p>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [leases, expiring, units, maintenance] = await Promise.all([
          fetch("/api/v1/leases?status=active&limit=1000").then((r) => r.json()),
          fetch("/api/v1/leases/expiring?days=90").then((r) => r.json()),
          fetch("/api/v1/units?status=available").then((r) => r.json()),
          fetch("/api/v1/maintenance?status=open&limit=1000").then((r) => r.json()),
        ]);

        setStats({
          activeLeases:    Array.isArray(leases)      ? leases.length      : 0,
          expiringLeases:  Array.isArray(expiring)    ? expiring.length    : 0,
          availableUnits:  Array.isArray(units)        ? units.length       : 0,
          openMaintenance: Array.isArray(maintenance)  ? maintenance.length : 0,
        });
      } catch {
        setError("Could not load data. Is the backend running?");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const display = (n: number) => (loading ? "—" : n);

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Portfolio overview</p>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-6 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {error}
        </div>
      )}

      {/* 4 Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        <StatCard
          label="Active Leases"
          value={display(stats?.activeLeases ?? 0)}
          icon={<FileText size={22} />}
          color="text-blue-600"
          bg="bg-blue-50"
        />
        <StatCard
          label="Expiring Leases"
          value={display(stats?.expiringLeases ?? 0)}
          icon={<AlertTriangle size={22} />}
          color="text-amber-600"
          bg="bg-amber-50"
        />
        <StatCard
          label="Available Units"
          value={display(stats?.availableUnits ?? 0)}
          icon={<Building2 size={22} />}
          color="text-emerald-600"
          bg="bg-emerald-50"
        />
        <StatCard
          label="Open Maintenance"
          value={display(stats?.openMaintenance ?? 0)}
          icon={<Wrench size={22} />}
          color="text-rose-600"
          bg="bg-rose-50"
        />
      </div>
    </div>
  );
}
