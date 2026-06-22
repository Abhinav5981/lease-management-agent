"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { PriorityBadge, MaintenanceStatusBadge } from "@/components/ui/Badge";
import { getMaintenance } from "@/lib/api";
import type { MaintenanceRequest, MaintenancePriority, MaintenanceStatus } from "@/types";

const PRIORITY_FILTERS: { label: string; value: MaintenancePriority | "all" }[] = [
  { label: "All",       value: "all" },
  { label: "Emergency", value: "emergency" },
  { label: "High",      value: "high" },
  { label: "Medium",    value: "medium" },
  { label: "Low",       value: "low" },
];

const STATUS_FILTERS: { label: string; value: MaintenanceStatus | "all" }[] = [
  { label: "All",         value: "all" },
  { label: "Open",        value: "open" },
  { label: "In Progress", value: "in_progress" },
  { label: "Completed",   value: "completed" },
];

export default function MaintenancePage() {
  const [requests, setRequests] = useState<MaintenanceRequest[]>([]);
  const [priority, setPriority] = useState<MaintenancePriority | "all">("all");
  const [status, setStatus] = useState<MaintenanceStatus | "all">("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMaintenance({ limit: 200 })
      .then(setRequests)
      .finally(() => setLoading(false));
  }, []);

  const filtered = requests.filter((r) => {
    if (priority !== "all" && r.priority !== priority) return false;
    if (status !== "all" && r.status !== status) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        r.reference_number.toLowerCase().includes(q) ||
        r.category.toLowerCase().includes(q) ||
        r.unit?.unit_number?.toLowerCase().includes(q) ||
        r.unit?.building?.name?.toLowerCase().includes(q) ||
        (r.assigned_to ?? "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Maintenance</h1>
        <p className="text-sm text-gray-500 mt-1">{filtered.length} requests</p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        {/* Priority tabs */}
        <div className="flex items-center bg-white rounded-lg border border-slate-200 p-1 gap-0.5">
          {PRIORITY_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setPriority(f.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                priority === f.value
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Status tabs */}
        <div className="flex items-center bg-white rounded-lg border border-slate-200 p-1 gap-0.5">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatus(f.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                status === f.value
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
            placeholder="Search ticket, property, vendor…"
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
                {[
                  "Ticket No.",
                  "Property",
                  "Category",
                  "Priority",
                  "Status",
                  "Assigned Vendor",
                ].map((h) => (
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
                    No requests found
                  </td>
                </tr>
              ) : (
                filtered.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/60 transition-colors">

                    {/* Ticket No. */}
                    <td className="px-4 py-3.5 font-mono text-xs text-slate-700 whitespace-nowrap">
                      {r.reference_number}
                    </td>

                    {/* Property */}
                    <td className="px-4 py-3.5 whitespace-nowrap">
                      {r.unit ? (
                        <div>
                          <p className="font-medium text-slate-800">{r.unit.unit_number}</p>
                          <p className="text-xs text-slate-400">{r.unit.building?.name}</p>
                        </div>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>

                    {/* Category */}
                    <td className="px-4 py-3.5 text-slate-600 capitalize whitespace-nowrap">
                      {r.category.replace(/_/g, " ")}
                    </td>

                    {/* Priority */}
                    <td className="px-4 py-3.5">
                      <PriorityBadge priority={r.priority} />
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3.5">
                      <MaintenanceStatusBadge status={r.status} />
                    </td>

                    {/* Assigned Vendor */}
                    <td className="px-4 py-3.5 text-slate-700 whitespace-nowrap">
                      {r.assigned_to ?? <span className="text-slate-400">Unassigned</span>}
                    </td>

                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
