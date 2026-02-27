"use client";

import { ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Header from "./Header";
import { useAuthSession } from "@/services/auth";

type AppShellProps = {
  children: ReactNode;
};

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useAuthSession();
  const logged = Boolean(session);
  const inLogin = pathname === "/login";
  const inAdmin = pathname.startsWith("/admin");
  const inDashboard = pathname === "/" || pathname.startsWith("/agenda") || pathname.startsWith("/gestao");
  const isPublicBookingPath =
    /^\/[^/]+$/.test(pathname) &&
    !["/login", "/admin", "/agenda", "/gestao"].includes(pathname);
  const needsAuth = inDashboard || inAdmin;
  const isAdmin = session?.tenantId === "admin";

  useEffect(() => {
    if (!logged && needsAuth) {
      router.replace("/login");
    }

    if (logged && inLogin) {
      router.replace(isAdmin ? "/admin" : "/");
    }

    if (logged && inAdmin && !isAdmin) {
      router.replace("/");
    }
  }, [router, logged, inLogin, isAdmin, inAdmin, needsAuth]);

  if ((!logged && needsAuth) || (logged && inLogin) || (logged && inAdmin && !isAdmin)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="spinner" aria-label="Carregando" />
      </div>
    );
  }

  return (
    <>
      {pathname !== "/login" && !isPublicBookingPath && <Header />}
      {children}
    </>
  );
}
