import { List, Moon, Robot, Sun, User, X } from "@phosphor-icons/react";
import { type ReactNode, useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router";
import { useCompany, useTool } from "../api/hooks";
import type { PendingAction } from "../api/types";
import { setActAs, setTheme, useSession } from "../app/session";
import { cx } from "../design/primitives";
import { NAV } from "./nav";

function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="relative block size-7 rounded-[9px] bg-on-panel/10">
        <span className="absolute left-[7px] top-[6px] h-4 w-1 rounded-full bg-on-panel" />
        <span className="absolute bottom-[6px] left-[13px] h-1 w-2 rounded-full bg-primary" />
      </span>
      <span className="text-[16px] font-medium tracking-[0.01em] text-on-panel">ledgerkit</span>
    </div>
  );
}

function Navigation({ pendingCount, onNavigate }: { pendingCount: number; onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-5">
      {NAV.map((group) => (
        <div key={group.label ?? "top"}>
          {group.label && <p className="mb-1 px-3 text-[12px] text-on-panel-2/70">{group.label}</p>}
          <ul className="flex flex-col gap-0.5">
            {group.items.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === "/"}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cx(
                      "relative flex h-8 items-center gap-2.5 rounded-full px-3 transition-colors duration-300 ease-out-soft",
                      isActive
                        ? "bg-on-panel/10 text-on-panel shadow-[inset_0_1px_0_rgb(255_255_255/0.06)] before:absolute before:-left-2 before:h-4 before:w-1 before:rounded-full before:bg-primary"
                        : "text-on-panel-2 hover:bg-on-panel/5 hover:text-on-panel",
                    )
                  }
                >
                  <item.icon size={17} />
                  <span className="flex-1">{item.label}</span>
                  {item.to === "/approvals" && pendingCount > 0 && (
                    <span className="figures rounded-full bg-primary px-1.5 text-[11.5px] font-medium leading-[18px] text-on-primary">
                      {pendingCount}
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function ActorSwitch() {
  const { actAs } = useSession();
  const options = [
    { id: "user" as const, label: "You", icon: User },
    { id: "agent" as const, label: "Agent", icon: Robot },
  ];
  return (
    <div role="group" aria-label="Act as" className="flex gap-1 rounded-full bg-on-panel/5 p-1">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={actAs === option.id}
          onClick={() => setActAs(option.id)}
          className={cx(
            "flex h-7 flex-1 items-center justify-center gap-1.5 rounded-full text-[13px] transition-colors duration-300 ease-out-soft",
            actAs === option.id ? "bg-on-panel/15 text-on-panel" : "text-on-panel-2 hover:text-on-panel",
          )}
        >
          <option.icon size={15} />
          {option.label}
        </button>
      ))}
    </div>
  );
}

function ThemeToggle() {
  const { theme } = useSession();
  const next = theme === "dark" ? "light" : "dark";
  const Glyph = theme === "dark" ? Sun : Moon;
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} theme`}
      className="flex size-9 shrink-0 items-center justify-center rounded-full bg-on-panel/5 text-on-panel-2 transition-colors duration-300 ease-out-soft hover:text-on-panel"
    >
      <Glyph size={17} />
    </button>
  );
}

function SidebarContent({ pendingCount, onNavigate }: { pendingCount: number; onNavigate?: () => void }) {
  const company = useCompany();
  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pb-5 pt-5">
        <Wordmark />
        <p className="mt-4 truncate rounded-2xl bg-on-panel/5 px-3 py-2.5 text-[13.5px] text-on-panel shadow-[inset_0_1px_0_rgb(255_255_255/0.05)]">{company.data?.name ?? " "}</p>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4 [scrollbar-color:color-mix(in_oklab,var(--on-panel)_20%,transparent)_transparent] [scrollbar-width:thin]">
        <Navigation pendingCount={pendingCount} onNavigate={onNavigate} />
      </div>
      <div className="flex items-center gap-2 p-3">
        <div className="flex-1">
          <ActorSwitch />
        </div>
        <ThemeToggle />
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { actAs } = useSession();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useLocation();
  const pending = useTool<{ actions: PendingAction[] }>("list_pending_approvals");
  const pendingCount = pending.data?.actions.length ?? 0;

  useEffect(() => {
    if (!drawerOpen) return;
    const close = (event: KeyboardEvent) => event.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [drawerOpen]);

  return (
    <div className="min-h-[100dvh]">
      {/* Desktop: the navigation is a floating panel, detached from the window edge. */}
      <aside className="fixed inset-y-3 left-3 z-20 hidden w-60 overflow-hidden rounded-[22px] bg-panel bg-[image:var(--panel-glow)] ring-1 ring-line lg:block">
        <SidebarContent pendingCount={pendingCount} />
      </aside>

      {/* Mobile: a compact bar and a drawer. */}
      <div className="sticky top-0 z-20 flex h-14 items-center justify-between bg-panel px-4 lg:hidden">
        <Wordmark />
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          aria-label="Open menu"
          className="flex size-9 items-center justify-center rounded-full bg-on-panel/5 text-on-panel"
        >
          <List size={18} />
        </button>
      </div>
      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setDrawerOpen(false)}
            className="absolute inset-0 animate-fade bg-[rgb(23_23_33/0.5)]"
          />
          <aside className="absolute inset-y-2 left-2 w-64 animate-rise overflow-hidden rounded-[22px] bg-panel bg-[image:var(--panel-glow)] shadow-float ring-1 ring-line">
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              aria-label="Close menu"
              className="absolute right-3 top-4 flex size-8 items-center justify-center rounded-full text-on-panel-2 hover:text-on-panel"
            >
              <X size={18} />
            </button>
            <SidebarContent pendingCount={pendingCount} onNavigate={() => setDrawerOpen(false)} />
          </aside>
        </div>
      )}

      <div className="lg:pl-[16.5rem]">
        {actAs === "agent" && (
          <div className="mx-4 mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-2xl bg-lavender px-4 py-2.5 sm:mx-8 lg:mr-3">
            <p className="flex items-center gap-2 text-ink">
              <Robot size={17} className="shrink-0 text-primary-ink" />
              You are acting as an agent. Postings, payments and voids are held for approval instead of running.
            </p>
            <button
              type="button"
              onClick={() => setActAs("user")}
              className="font-medium text-primary-ink underline-offset-4 hover:underline"
            >
              Switch back
            </button>
          </div>
        )}
        {/* Keyed by path so each screen fades in once on navigation. */}
        <main key={location.pathname} className="mx-auto w-full max-w-[1280px] animate-fade px-4 pb-16 pt-9 sm:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
