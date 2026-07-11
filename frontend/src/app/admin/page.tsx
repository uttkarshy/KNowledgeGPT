"use client";

import { AlertTriangle, Ban, CheckCircle2, Database, FileStack, MessageSquare, Search, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { formatBytes, formatRelativeTime } from "@/lib/format";
import {
  useAdminUsers,
  useAnalytics,
  useDeleteUser,
  useErrorLogs,
  useSuspendUser,
  useUnsuspendUser,
} from "@/hooks/use-admin";
import type { AdminUser } from "@/types";

function StatCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: React.ElementType }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-mist-200 bg-white p-4 dark:border-ink-700 dark:bg-ink-900">
      <div className="flex h-9 w-9 items-center justify-center rounded-md bg-stamp-teal/10 text-stamp-teal">
        <Icon size={17} />
      </div>
      <div>
        <div className="font-display text-xl text-ink-900 dark:text-mist-50">{value}</div>
        <div className="font-mono text-[11px] text-ink-500">{label}</div>
      </div>
    </div>
  );
}

function UserRow({ user }: { user: AdminUser }) {
  const suspend = useSuspendUser();
  const unsuspend = useUnsuspendUser();
  const deleteUser = useDeleteUser();

  return (
    <tr className="border-b border-mist-200 last:border-0 dark:border-ink-700">
      <td className="py-2.5 pr-4">
        <div className="text-sm text-ink-900 dark:text-mist-50">{user.full_name || "—"}</div>
        <div className="font-mono text-[11px] text-ink-500">{user.email}</div>
      </td>
      <td className="py-2.5 pr-4">
        <span className="rounded bg-mist-100 px-1.5 py-0.5 font-mono text-[10px] uppercase text-ink-700 dark:bg-ink-800 dark:text-mist-100">
          {user.role}
        </span>
      </td>
      <td className="py-2.5 pr-4">
        {user.is_suspended ? (
          <span className="flex items-center gap-1 text-xs text-danger">
            <Ban size={12} /> Suspended
          </span>
        ) : user.is_verified ? (
          <span className="flex items-center gap-1 text-xs text-success">
            <CheckCircle2 size={12} /> Active
          </span>
        ) : (
          <span className="text-xs text-ink-500">Unverified</span>
        )}
      </td>
      <td className="py-2.5 pr-4 font-mono text-[11px] text-ink-500">
        {user.last_login_at ? formatRelativeTime(user.last_login_at) : "Never"}
      </td>
      <td className="py-2.5 text-right">
        <div className="flex justify-end gap-1.5">
          {user.role !== "admin" && (
            <>
              {user.is_suspended ? (
                <button
                  onClick={() => unsuspend.mutate(user.id)}
                  className="rounded px-2 py-1 text-xs text-stamp-teal hover:bg-stamp-teal/10"
                >
                  Unsuspend
                </button>
              ) : (
                <button
                  onClick={() => suspend.mutate(user.id)}
                  className="rounded px-2 py-1 text-xs text-ink-500 hover:bg-mist-100 dark:hover:bg-ink-800"
                >
                  Suspend
                </button>
              )}
              <button
                onClick={() => {
                  if (confirm(`Permanently delete ${user.email} and all their data?`)) {
                    deleteUser.mutate(user.id);
                  }
                }}
                className="rounded p-1.5 text-danger hover:bg-danger/10"
                aria-label={`Delete ${user.email}`}
              >
                <Trash2 size={13} />
              </button>
            </>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function AdminPage() {
  const [search, setSearch] = useState("");
  const { data: analytics } = useAnalytics();
  const { data: users = [] } = useAdminUsers(search);
  const { data: errorLogs = [] } = useErrorLogs();

  return (
    <main className="min-h-screen bg-mist-50 p-6 dark:bg-ink-950">
      <div className="mx-auto max-w-6xl space-y-8">
        <div>
          <h1 className="font-display text-2xl text-ink-900 dark:text-mist-50">Admin</h1>
          <p className="mt-1 text-sm text-ink-500">System-wide analytics, user management, and error monitoring.</p>
        </div>

        <section>
          <h2 className="font-mono text-xs uppercase tracking-wide text-ink-500">Overview</h2>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Users" value={analytics?.total_users ?? "—"} icon={Users} />
            <StatCard label="Knowledge bases" value={analytics?.total_knowledge_bases ?? "—"} icon={Database} />
            <StatCard label="Documents" value={analytics?.total_documents ?? "—"} icon={FileStack} />
            <StatCard label="Chat sessions" value={analytics?.total_chat_sessions ?? "—"} icon={MessageSquare} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatCard label="Storage used" value={analytics ? formatBytes(analytics.total_storage_bytes) : "—"} icon={Database} />
            <StatCard label="API calls (24h)" value={analytics?.api_calls_last_24h ?? "—"} icon={CheckCircle2} />
            <StatCard
              label="Errors (24h)"
              value={analytics?.api_errors_last_24h ?? "—"}
              icon={AlertTriangle}
            />
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between">
            <h2 className="font-mono text-xs uppercase tracking-wide text-ink-500">Users</h2>
          </div>
          <div className="mt-2 flex items-center gap-2 rounded-md border border-mist-200 bg-white px-3 py-2 dark:border-ink-700 dark:bg-ink-900">
            <Search size={14} className="text-ink-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by email…"
              className="flex-1 bg-transparent text-sm outline-none"
            />
          </div>
          <div className="mt-2 overflow-x-auto rounded-md border border-mist-200 bg-white p-4 dark:border-ink-700 dark:bg-ink-900">
            <table className="w-full">
              <thead>
                <tr className="border-b border-mist-200 text-left font-mono text-[10px] uppercase tracking-wide text-ink-500 dark:border-ink-700">
                  <th className="pb-2">User</th>
                  <th className="pb-2">Role</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Last login</th>
                  <th className="pb-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <UserRow key={user.id} user={user} />
                ))}
              </tbody>
            </table>
            {users.length === 0 && <p className="py-4 text-center text-sm text-ink-500">No users found.</p>}
          </div>
        </section>

        <section>
          <h2 className="font-mono text-xs uppercase tracking-wide text-ink-500">Recent errors</h2>
          <div className="mt-2 overflow-x-auto rounded-md border border-mist-200 bg-white p-4 dark:border-ink-700 dark:bg-ink-900">
            <table className="w-full">
              <thead>
                <tr className="border-b border-mist-200 text-left font-mono text-[10px] uppercase tracking-wide text-ink-500 dark:border-ink-700">
                  <th className="pb-2">Endpoint</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Latency</th>
                  <th className="pb-2">When</th>
                </tr>
              </thead>
              <tbody>
                {errorLogs.map((log) => (
                  <tr key={log.id} className="border-b border-mist-200 last:border-0 dark:border-ink-700">
                    <td className="py-2 font-mono text-xs text-ink-700 dark:text-mist-100">{log.endpoint}</td>
                    <td className="py-2 font-mono text-xs text-danger">{log.status_code}</td>
                    <td className="py-2 font-mono text-xs text-ink-500">{log.latency_ms ?? "—"}ms</td>
                    <td className="py-2 font-mono text-xs text-ink-500">{formatRelativeTime(log.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {errorLogs.length === 0 && <p className="py-4 text-center text-sm text-ink-500">No errors recently. Good sign.</p>}
          </div>
        </section>
      </div>
    </main>
  );
}
