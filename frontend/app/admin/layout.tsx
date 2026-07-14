"use client";

import { ReactNode, useEffect, useSyncExternalStore } from "react";
import { usePathname, useRouter } from "next/navigation";

import Loading from "../components/Loading";
import { useAuthSession } from "@/services/auth";


type AdminLayoutProps = {
  children: ReactNode;
};

const subscribeToMount = () => () => {};

export default function AdminLayout({ children }: AdminLayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useAuthSession();
  const mounted = useSyncExternalStore(subscribeToMount, () => true, () => false);

  useEffect(() => {
    if (!mounted) return;

    if (!session) {
      router.replace("/login");
      return;
    }

    if (pathname.startsWith("/admin/master") && session.tenantId !== "admin") {
      router.replace("/admin");
    }
  }, [mounted, pathname, router, session]);

  if (!mounted || !session) {
    return <Loading />;
  }

  if (pathname.startsWith("/admin/master") && session.tenantId !== "admin") {
    return <Loading />;
  }

  return <>{children}</>;
}
