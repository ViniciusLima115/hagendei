"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  confirmarPresenca,
  listNotificacoes,
  marcarNotificacaoLida,
  marcarTodasNotificacoesLidas,
  Notificacao,
} from "@/services/api";
import { getAuthSession, useAuthSession } from "@/services/auth";

const POLL_INTERVAL_MS = 15_000;

function getSeenStorageKey(): string {
  const tenantId = getAuthSession()?.tenantId ?? "anon";
  return `notif_seen_${tenantId}`;
}

function loadSeenIds(): Set<number> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = localStorage.getItem(getSeenStorageKey());
    if (!raw) return new Set();
    return new Set(JSON.parse(raw) as number[]);
  } catch {
    return new Set();
  }
}

function saveSeenIds(ids: Set<number>): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(getSeenStorageKey(), JSON.stringify([...ids]));
  } catch {
    // ignore
  }
}

export interface UseNotificacoesReturn {
  notificacoes: Notificacao[];
  naoLidas: number;
  toastsNovos: Notificacao[];
  marcarLida: (id: number) => Promise<void>;
  marcarTodasLidas: () => Promise<void>;
  confirmarPresencaNotif: (agendamentoId: number, compareceu: boolean) => Promise<void>;
  limparToast: (id: number) => void;
  marcarNovoAgendamentoLido: () => Promise<void>;
}

export function useNotificacoes(): UseNotificacoesReturn {
  const session = useAuthSession();
  const tenantId = session?.tenantId && /^\d+$/.test(session.tenantId) ? session.tenantId : null;
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [toastsNovos, setToastsNovos] = useState<Notificacao[]>([]);
  const [stateTenantId, setStateTenantId] = useState<string | null>(null);
  const seenIds = useRef<Set<number>>(new Set());
  const initialized = useRef(false);
  const activeTenantId = useRef<string | null>(null);

  const fetchNotificacoes = useCallback(async () => {
    if (!tenantId) return;
    if (activeTenantId.current !== tenantId) {
      activeTenantId.current = tenantId;
      initialized.current = false;
      seenIds.current = new Set();
      setToastsNovos([]);
    }
    try {
      const data = await listNotificacoes(false, 30);
      if (getAuthSession()?.tenantId !== tenantId) return;
      setNotificacoes(data);
      setStateTenantId(tenantId);

      // Inicializa seenIds do localStorage na primeira chamada
      if (!initialized.current) {
        initialized.current = true;
        seenIds.current = loadSeenIds();
      }

      const novas = data.filter((n) => !seenIds.current.has(n.id));
      if (novas.length > 0) {
        seenIds.current = new Set([...seenIds.current, ...novas.map((n) => n.id)]);
        saveSeenIds(seenIds.current);
        setToastsNovos((prev) => {
          const merged = [...prev, ...novas];
          return merged.slice(-3);
        });
      }
    } catch (err) {
      console.error("[notificacoes] falha ao buscar notificações:", err);
    }
  }, [tenantId]);

  useEffect(() => {
    if (!tenantId) {
      activeTenantId.current = null;
      initialized.current = false;
      seenIds.current = new Set();
      return;
    }
    const frame = window.requestAnimationFrame(fetchNotificacoes);
    const interval = setInterval(fetchNotificacoes, POLL_INTERVAL_MS);
    return () => {
      window.cancelAnimationFrame(frame);
      clearInterval(interval);
    };
  }, [fetchNotificacoes, tenantId]);

  const notificacoesDoTenant = useMemo(
    () => (stateTenantId === tenantId ? notificacoes : []),
    [notificacoes, stateTenantId, tenantId],
  );
  const toastsDoTenant = useMemo(
    () => (stateTenantId === tenantId ? toastsNovos : []),
    [stateTenantId, tenantId, toastsNovos],
  );

  const marcarLida = useCallback(async (id: number) => {
    const updated = await marcarNotificacaoLida(id);
    setNotificacoes((prev) =>
      prev.map((n) => (n.id === id ? updated : n))
    );
  }, []);

  const marcarTodasLidas = useCallback(async () => {
    await marcarTodasNotificacoesLidas();
    setNotificacoes((prev) => prev.map((n) => ({ ...n, lida: true })));
  }, []);

  // Marca como lidas todas as notificações de novo_agendamento não lidas (chamado ao abrir o sino)
  const marcarNovoAgendamentoLido = useCallback(async () => {
    const naoLidasNovos = notificacoesDoTenant.filter(
      (n) => n.tipo === "novo_agendamento" && !n.lida
    );
    await Promise.all(naoLidasNovos.map((n) => marcarNotificacaoLida(n.id)));
    if (naoLidasNovos.length > 0) {
      setNotificacoes((prev) =>
        prev.map((n) =>
          n.tipo === "novo_agendamento" ? { ...n, lida: true } : n
        )
      );
    }
  }, [notificacoesDoTenant]);

  const confirmarPresencaNotif = useCallback(
    async (agendamentoId: number, compareceu: boolean) => {
      await confirmarPresenca(agendamentoId, compareceu);
      await fetchNotificacoes();
      // Dispara evento para que o dashboard saiba que deve recarregar
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("presenca-confirmada"));
      }
    },
    [fetchNotificacoes]
  );

  const limparToast = useCallback((id: number) => {
    setToastsNovos((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const naoLidas = notificacoesDoTenant.filter((n) => !n.lida).length;

  return {
    notificacoes: notificacoesDoTenant,
    naoLidas,
    toastsNovos: toastsDoTenant,
    marcarLida,
    marcarTodasLidas,
    confirmarPresencaNotif,
    limparToast,
    marcarNovoAgendamentoLido,
  };
}
