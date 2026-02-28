"use client";

import Loading from "../components/Loading";
import GestaoPage from "../gestao/page";
import SuperAdminPage from "./master/page";
import { useAuthSession } from "@/services/auth";

export default function AdminEntryPage() {
  const session = useAuthSession();

  if (!session) {
    return <Loading />;
  }

  if (session.tenantId === "admin") {
    return <SuperAdminPage />;
  }

  return <GestaoPage />;
}
