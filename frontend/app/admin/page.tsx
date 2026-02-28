"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Loading from "../components/Loading";
import GestaoPage from "../gestao/page";
import SuperAdminPage from "./master/page";
import { useAuthSession } from "@/services/auth";

export default function AdminEntryPage() {
  const router = useRouter();
  const session = useAuthSession();

  useEffect(() => {
    if (!session) {
      router.replace("/login");
    }
  }, [router, session]);

  if (!session) {
    return <Loading />;
  }

  if (session.tenantId === "admin") {
    return <SuperAdminPage />;
  }

  return <GestaoPage />;
}
