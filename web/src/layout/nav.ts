import {
  ArrowsLeftRight,
  ChartLineUp,
  ClockCounterClockwise,
  FileText,
  GearSix,
  HouseSimple,
  type Icon,
  Kanban,
  Notebook,
  Package,
  Percent,
  Receipt,
  Scales,
  SealCheck,
  ShoppingBagOpen,
  Storefront,
  TerminalWindow,
  TreeStructure,
  UserPlus,
  UsersThree,
  Invoice,
} from "@phosphor-icons/react";

export type NavItem = { to: string; label: string; icon: Icon };
export type NavGroup = { label: string | null; items: NavItem[] };

export const NAV: NavGroup[] = [
  { label: null, items: [{ to: "/", label: "Dashboard", icon: HouseSimple }] },
  {
    label: "Sales",
    items: [
      { to: "/invoices", label: "Invoices", icon: Invoice },
      { to: "/quotations", label: "Quotations", icon: FileText },
      { to: "/orders", label: "Orders", icon: ShoppingBagOpen },
      { to: "/customers", label: "Customers", icon: UsersThree },
      { to: "/pipeline", label: "Pipeline", icon: Kanban },
      { to: "/leads", label: "Leads", icon: UserPlus },
    ],
  },
  {
    label: "Purchases",
    items: [
      { to: "/bills", label: "Bills", icon: Receipt },
      { to: "/vendors", label: "Vendors", icon: Storefront },
    ],
  },
  {
    label: "Money",
    items: [
      { to: "/payments", label: "Payments", icon: ArrowsLeftRight },
      { to: "/reports", label: "Reports", icon: ChartLineUp },
    ],
  },
  {
    label: "Accounting",
    items: [
      { to: "/journal", label: "Journal", icon: Notebook },
      { to: "/accounts", label: "Accounts", icon: TreeStructure },
      { to: "/trial-balance", label: "Trial balance", icon: Scales },
      { to: "/items", label: "Items", icon: Package },
      { to: "/tax-rates", label: "Tax rates", icon: Percent },
    ],
  },
  {
    label: "Control",
    items: [
      { to: "/approvals", label: "Approvals", icon: SealCheck },
      { to: "/audit", label: "Audit log", icon: ClockCounterClockwise },
      { to: "/console", label: "Tool console", icon: TerminalWindow },
      { to: "/settings", label: "Settings", icon: GearSix },
    ],
  },
];
