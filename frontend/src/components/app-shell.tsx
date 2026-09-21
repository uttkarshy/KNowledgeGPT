"use client";

import { BookOpen, Coins, Menu, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Brand } from "@/components/brand";
import { SignOutButton } from "@/components/sign-out-button";
import { useCredits } from "@/hooks/use-billing";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const credits = useCredits();

  const nav = [
    { label: "Knowledge bases", href: "/dashboard", icon: BookOpen, active: pathname === "/dashboard" },
    ...(pathname === "/admin" ? [{ label: "Admin", href: "/admin", icon: ShieldCheck, active: true }] : []),
  ];

  const navigation = (
    <>
      <div className="px-4 pb-5 pt-5 lg:px-5 lg:pt-7">
        <Brand />
      </div>
      <nav className="flex-1 space-y-1 px-3" aria-label="Main navigation">
        {nav.map(({ label, href, icon: Icon, active }) => (
          <Link
            key={href}
            href={href}
            onClick={() => setMobileOpen(false)}
            className={`flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
              active
                ? "bg-white text-ink-950 shadow-sm ring-1 ring-ink-950/[0.06] dark:bg-ink-800 dark:text-white dark:ring-white/10"
                : "text-ink-500 hover:bg-white/70 hover:text-ink-900 dark:hover:bg-white/5 dark:hover:text-white"
            }`}
          >
            <Icon size={17} strokeWidth={1.8} />
            {label}
          </Link>
        ))}
        <Link
          href="/dashboard#credits"
          onClick={() => setMobileOpen(false)}
          className="flex items-center justify-between rounded-xl px-3 py-2.5 text-sm font-medium text-ink-500 transition hover:bg-white/70 hover:text-ink-900 dark:hover:bg-white/5 dark:hover:text-white"
        >
          <span className="flex items-center gap-2.5">
            <Coins size={17} strokeWidth={1.8} /> Credits
          </span>
          {credits.data && (
            <span className="rounded-full bg-stamp-teal/10 px-2 py-0.5 font-mono text-[11px] font-medium text-stamp-teal">
              {credits.data.balance}
            </span>
          )}
        </Link>
      </nav>
      <div className="border-t border-ink-950/[0.06] p-3 dark:border-white/10">
        <SignOutButton />
      </div>
    </>
  );

  return (
    <div className="min-h-dvh bg-canvas text-ink-700 dark:bg-ink-950 dark:text-mist-100">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-ink-950/[0.06] bg-mist-50/80 backdrop-blur-xl dark:border-white/10 dark:bg-ink-900/90 lg:flex">
        {navigation}
      </aside>

      <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-ink-950/[0.06] bg-canvas/90 px-4 backdrop-blur-xl dark:border-white/10 dark:bg-ink-950/90 lg:hidden">
        <Brand />
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-ink-950/10 bg-white text-ink-700 shadow-sm dark:border-white/10 dark:bg-ink-900 dark:text-white"
          aria-label="Open navigation"
        >
          <Menu size={19} />
        </button>
      </header>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button className="absolute inset-0 bg-ink-950/40 backdrop-blur-sm" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />
          <aside className="relative flex h-full w-[min(19rem,86vw)] flex-col bg-mist-50 shadow-2xl dark:bg-ink-900">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="absolute right-3 top-4 flex h-9 w-9 items-center justify-center rounded-lg text-ink-500 hover:bg-white"
              aria-label="Close navigation"
            >
              <X size={18} />
            </button>
            {navigation}
          </aside>
        </div>
      )}

      <div className="lg:pl-60">{children}</div>
    </div>
  );
}
