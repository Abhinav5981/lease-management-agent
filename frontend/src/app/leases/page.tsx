"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { LeaseStatusBadge } from "@/components/ui/Badge";
import { getLeases } from "@/lib/api";
import type { Lease } from "@/types";

const FILTERS = [
  { label: "All",        key: "all" },
  { label: "Active",     key: "active" },
  { label: "Expiring",   key: "expiring" },
  { label: "Renewed",    key: "renewed" },
  { label: "Terminated", key: "terminated" },
] as const;

type FilterKey = typeof FILTERS[number]["key"];

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
  });
}

function daysUntil(iso: string) {
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

function applyFilter(leases: Lease[], key: FilterKey): Lease[] {
  switch (key) {
    case "active":     return leases.filter((l) => l.status === "active" && daysUntil(l.end_date) > 90);
    case "expiring":   return leases.filter((l) => l.status === "active" && daysUntil(l.end_date) <= 90);
    case "renewed":    return leases.filter((l) => (l.status as string) === "renewed");
    case "terminated": return leases.filter((l) => l.status === "terminated");
    default:           return leases;
  }
}

export default function LeasesPage() {
  const [leases, setLeases] = useState<Lease[]>([]);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getLeases({ limit: 500 })
      .then(setLeases)
      .finally(() => setLoading(false));
  }, []);

  const filtered = applyFilter(leases, filter).filter((l) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      l.lease_number.toLowerCase().includes(q) ||
      l.tenant?.first_name?.toLowerCase().includes(q) ||
      l.tenant?.last_name?.toLowerCase().includes(q) ||
      l.unit?.unit_number?.toLowerCase().includes(q) ||
      l.unit?.building?.name?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Lease Management</h1>
        <p className="text-sm text-gray-500 mt-1">{filtered.length} leases</p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        {/* Filter tabs */}
        <div className="flex items-center bg-white rounded-lg border border-slate-200 p-1 gap-0.5">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                filter === f.key
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search lease, tenant, unit…"
            className="pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-lg bg-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 w-56"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                {["Lease ID", "Tenant", "Unit", "Start Date", "End Date", "Status"].map((h) => (
                  <th
                    key={h}
                    className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-400">
                    Loading…
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-sm text-slate-400">
                    No leases found
                  </td>
                </tr>
              ) : (
                filtered.map((l) => {
                  const expiring = l.status === "active" && daysUntil(l.end_date) <= 30;
                  return (
                    <tr key={l.id} className="hover:bg-slate-50/60 transition-colors">
                      {/* Lease ID */}
                      <td className="px-4 py-3.5 font-mono text-xs text-slate-700 whitespace-nowrap">
                        {l.lease_number}
                      </td>

                      {/* Tenant */}
                      <td className="px-4 py-3.5 whitespace-nowrap">
                        {l.tenant ? (
                          <span className="font-medium text-slate-800">
                            {l.tenant.first_name} {l.tenant.last_name}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* Unit */}
                      <td className="px-4 py-3.5 whitespace-nowrap">
                        {l.unit ? (
                          <div>
                            <p className="font-medium text-slate-800">{l.unit.unit_number}</p>
                            <p className="text-xs text-slate-400">{l.unit.building?.name}</p>
                          </div>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* Start Date */}
                      <td className="px-4 py-3.5 text-slate-600 whitespace-nowrap">
                        {formatDate(l.start_date)}
                      </td>

                      {/* End Date */}
                      <td className="px-4 py-3.5 whitespace-nowrap">
                        <span className={expiring ? "text-red-600 font-semibold" : "text-slate-600"}>
                          {formatDate(l.end_date)}
                        </span>
                        {expiring && (
                          <p className="text-xs text-red-500">{daysUntil(l.end_date)}d left</p>
                        )}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3.5">
                        <LeaseStatusBadge status={l.status} />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
