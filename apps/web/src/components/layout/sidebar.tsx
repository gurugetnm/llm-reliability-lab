import { Brand } from "@/components/layout/brand";
import { NavList } from "@/components/layout/nav-list";

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
      <div className="flex h-14 items-center border-b border-sidebar-border px-2">
        <Brand />
      </div>
      <div className="flex-1 overflow-y-auto py-3">
        <NavList />
      </div>
      <div className="border-t border-sidebar-border px-4 py-3">
        <p className="text-xs text-sidebar-foreground/40">
          v0.1.0 &middot; local-first
        </p>
      </div>
    </aside>
  );
}
