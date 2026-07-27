"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { logout } from "@/services/auth";
import ThemeToggle from "./ThemeToggle";
import { NotificacoesSino } from "./NotificacoesSino";
import { useNotificacoesContext } from "./NotificacoesProvider";
import styles from "./TopBar.module.css";

type TopBarProps = {
  tenantName: string;
  sectionLabel: string;
};

export default function TopBar({ tenantName, sectionLabel }: TopBarProps) {
  const router = useRouter();
  const notif = useNotificacoesContext();

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className={styles.topBar}>
      <div className={styles.titles}>
        <span className={styles.tenantName}>{tenantName}</span>
        <span className={styles.sectionLabel}>{sectionLabel}</span>
      </div>

      <div className={styles.actions}>
        <ThemeToggle />

        <NotificacoesSino
          notificacoes={notif.notificacoes}
          naoLidas={notif.naoLidas}
          marcarLida={notif.marcarLida}
          marcarTodasLidas={notif.marcarTodasLidas}
          confirmarPresencaNotif={notif.confirmarPresencaNotif}
          marcarNovoAgendamentoLido={notif.marcarNovoAgendamentoLido}
        />

        <button type="button" className={styles.logoutButton} onClick={handleLogout}>
          <LogOut size={16} />
          <span>Sair</span>
        </button>
      </div>
    </header>
  );
}
