"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Wrench,
  MessageSquare,
  Building2,
} from "lucide-react";

const NAV = [
  { href: "/dashboard",    label: "Dashboard",         icon: LayoutDashboard },
  { href: "/leases",       label: "Lease Management",  icon: FileText },
  { href: "/maintenance",  label: "Maintenance",        icon: Wrench },
  { href: "/assistant",    label: "AI Assistant",       icon: MessageSquare },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 shrink-0 bg-slate-900 flex flex-col h-full">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-slate-700/60">
        <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center shrink-0">
          <Building2 size={16} className="text-white" />
        </div>
        <div>
          <p className="text-white text-sm font-semibold leading-tight">Lease Manager</p>
          <p className="text-slate-400 text-xs">Dubai Real Estate</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-slate-700/60">
        <p className="text-slate-500 text-xs">v1.0.0 · MVP</p>
      </div>
    </aside>
  );
}
