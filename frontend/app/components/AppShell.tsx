"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import {
  BarChart2,
  CalendarDays,
  LayoutDashboard,
  Settings,
  Settings2,
  Shield,
} from "lucide-react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { useTenantTheme } from "@/hooks/useTenantTheme";
import { useAuthSession } from "@/services/auth";
import { NotificacoesProvider } from "./NotificacoesProvider";
import styles from "./AppShell.module.css";

type AppShellProps = {
  children: ReactNode;
};

const TOKEN_ACTION_PREFIXES = ["/confirmar/", "/cancelar/", "/reagendar/"];

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  useTenantTheme();
  const session = useAuthSession();

  const inLogin = pathname === "/login";
  const isPublicBookingById = pathname.startsWith("/agendar/");
  const isTokenActionPage = TOKEN_ACTION_PREFIXES.some((p) => pathname.startsWith(p));
  const isPaymentReturnPage = pathname.startsWith("/agendamento/pagamento/");
  const ADMIN_PATHS = ["/login", "/admin", "/agenda", "/gestao", "/dashboard", "/configuracoes", "/upgrade", "/painel"];
  const isPublicBookingPath =
    !isPublicBookingById &&
    !isTokenActionPage &&
    /^\/[^/]+$/.test(pathname) &&
    !ADMIN_PATHS.includes(pathname);

  const hideNav =
    inLogin ||
    isPublicBookingPath ||
    isPublicBookingById ||
    isTokenActionPage ||
    isPaymentReturnPage;

  const isAdmin = session?.tenantId === "admin";
  const inAdminPage = pathname.startsWith("/admin");
  const navItems = [
    { href: "/", label: "Painel", icon: LayoutDashboard },
    { href: "/agenda", label: "Agenda", icon: CalendarDays },
    { href: "/gestao", label: "Gestao", icon: Settings2 },
    ...(!isAdmin && session && session.plan !== "gratis"
      ? [{ href: "/dashboard", label: "Dashboard", icon: BarChart2 }]
      : []),
    ...(!isAdmin ? [{ href: "/configuracoes", label: "Config.", icon: Settings }] : []),
    ...(isAdmin && !inAdminPage ? [{ href: "/admin", label: "Admin", icon: Shield }] : []),
  ];
  const activeItem = navItems.find((item) => item.href === pathname);
  const tenantName = session?.tenantName ?? "Estabelecimento";

  if (hideNav) {
    return children;
  }

  return (
    <NotificacoesProvider>
      <div className={styles.shell}>
        <Sidebar navItems={inAdminPage ? [] : navItems} />
        <div className={styles.mainColumn}>
          <TopBar tenantName={tenantName} sectionLabel={activeItem?.label ?? tenantName} />
          <div className={styles.content}>{children}</div>
        </div>
      </div>
    </NotificacoesProvider>
  );
}
