import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  FolderKanban,
  FlaskConical,
  Database,
  Cpu,
  CheckSquare,
  Activity,
  Settings,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  description: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    title: "Dashboard",
    href: "/",
    icon: LayoutDashboard,
    description: "Overview of your lab",
  },
  {
    title: "Projects",
    href: "/projects",
    icon: FolderKanban,
    description: "Group experiments by project",
  },
  {
    title: "Experiments",
    href: "/experiments",
    icon: FlaskConical,
    description: "Run and compare prompt/model configurations",
  },
  {
    title: "Datasets",
    href: "/datasets",
    icon: Database,
    description: "Manage evaluation and RAG datasets",
  },
  {
    title: "Models",
    href: "/models",
    icon: Cpu,
    description: "Local and remote LLM providers",
  },
  {
    title: "Evaluations",
    href: "/evaluations",
    icon: CheckSquare,
    description: "Score and compare experiment runs",
  },
  {
    title: "Traces",
    href: "/traces",
    icon: Activity,
    description: "Inspect request/response execution traces",
  },
  {
    title: "Settings",
    href: "/settings",
    icon: Settings,
    description: "Workspace and provider configuration",
  },
];
