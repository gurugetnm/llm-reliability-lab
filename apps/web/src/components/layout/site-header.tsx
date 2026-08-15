"use client";

import * as React from "react";
import { Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/theme-toggle";
import { Brand } from "@/components/layout/brand";
import { NavList } from "@/components/layout/nav-list";

export function SiteHeader() {
  const [open, setOpen] = React.useState(false);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4 md:justify-end">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          render={
            <Button variant="ghost" size="icon" className="size-8 md:hidden" aria-label="Open navigation" />
          }
        >
          <Menu className="size-4" />
        </SheetTrigger>
        <SheetContent side="left" className="w-64 bg-sidebar p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <div className="flex h-14 items-center border-b border-sidebar-border px-2">
            <Brand />
          </div>
          <div className="flex-1 overflow-y-auto py-3">
            <NavList onNavigate={() => setOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      <ThemeToggle />
    </header>
  );
}
