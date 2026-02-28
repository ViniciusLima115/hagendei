"use client";

import { ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import Loading from "../components/Loading";
import { useAuthSession } from "@/services/auth";


type AdminLayoutProps = {
  children: ReactNode;
};


export default function AdminLayout({ children }: AdminLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useAuthSession();

  useEffect(() => {
    if (!session) {
      router.replace("/login");
      return;
    }

    if (pathname.startsWith("/admin/master") && session.tenantId !== "admin") {
      router.replace("/admin");
    }
  }, [pathname, router, session]);

  if (!session) {
    return <Loading />;
  }

  if (pathname.startsWith("/admin/master") && session.tenantId !== "admin") {
    return <Loading />;
  }

  return <>{children}</>;
}
