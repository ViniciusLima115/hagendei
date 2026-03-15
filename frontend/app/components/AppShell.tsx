"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import Header from "./Header";
import ThemeToggle from "./ThemeToggle";

type AppShellProps = {
  children: ReactNode;
};

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const inLogin = pathname === "/login";
  const isPublicBookingById = pathname.startsWith("/agendar/");
  const isPublicBookingPath =
    !isPublicBookingById &&
    /^\/[^/]+$/.test(pathname) &&
    !["/login", "/admin", "/agenda", "/gestao"].includes(pathname);

  return (
    <>
      {!inLogin && !isPublicBookingPath && !isPublicBookingById && <Header />}
      {(inLogin || isPublicBookingPath || isPublicBookingById) && <ThemeToggle floating />}
      {children}
    </>
  );
}
