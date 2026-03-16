"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  cancelBookingByToken,
  confirmBookingByToken,
  getBookingByToken,
  PublicAgendamentoTokenResponse,
  requestRescheduleByToken,
} from "@/services/api";

type BookingActionMode = "confirmar" | "cancelar" | "reagendar";

type BookingTokenActionCardProps = {
  token: string;
  mode: BookingActionMode;
};

function formatarDataHora(valor: string) {
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor;
  return data.toLocaleString("pt-BR", {
    dateStyle: "full",
    timeStyle: "short",
  });
}

function labelStatus(status: PublicAgendamentoTokenResponse["status"]) {
  const mapa = {
    pendente: "Pendente",
    confirmado: "Confirmado",
    cancelado: "Cancelado",
    reagendamento_solicitado: "Reagendamento solicitado",
  };
  return mapa[status] ?? status;
}

function montarLinkAgendamento(dados: PublicAgendamentoTokenResponse | null) {
  if (!dados) return "/";
  if (dados.slug) return `/${dados.slug}`;
  return `/agendar/${dados.barbearia_id}`;
}

export default function BookingTokenActionCard({
  token,
  mode,
}: BookingTokenActionCardProps) {
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [dados, setDados] = useState<PublicAgendamentoTokenResponse | null>(null);

  useEffect(() => {
    let ativo = true;

    async function carregar() {
      setLoading(true);
      setErro(null);
      try {
        const resposta = await getBookingByToken(token);
        if (!ativo) return;
        setDados(resposta);
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Nao foi possivel carregar o agendamento.");
      } finally {
        if (ativo) setLoading(false);
      }
    }

    carregar();
    return () => {
      ativo = false;
    };
  }, [token]);

  const config = useMemo(() => {
    if (mode === "confirmar") {
      return {
        titulo: "Confirmar presenca",
        descricao: "Valide sua presenca para que a barbearia saiba que voce vem.",
        botao: "Confirmar agora",
        executar: confirmBookingByToken,
        sucesso: "Presenca confirmada com sucesso.",
      };
    }
    if (mode === "cancelar") {
      return {
        titulo: "Cancelar agendamento",
        descricao: "Se voce nao puder comparecer, cancele por aqui em poucos segundos.",
        botao: "Cancelar horario",
        executar: cancelBookingByToken,
        sucesso: "Agendamento cancelado com sucesso.",
      };
    }
    return {
      titulo: "Solicitar reagendamento",
      descricao: "Marque seu pedido de reagendamento e depois escolha um novo horario.",
      botao: "Solicitar reagendamento",
      executar: requestRescheduleByToken,
      sucesso: "Pedido de reagendamento registrado.",
    };
  }, [mode]);

  async function onAction() {
    setSubmitting(true);
    setErro(null);
    setSucesso(null);
    try {
      const resposta = await config.executar(token);
      setDados(resposta);
      setSucesso(config.sucesso);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Nao foi possivel concluir a acao.");
    } finally {
      setSubmitting(false);
    }
  }

  const linkAgendamento = montarLinkAgendamento(dados);

  return (
    <main className="min-h-screen bg-[var(--theme-canvas)] px-4 py-10">
      <section className="mx-auto max-w-3xl overflow-hidden rounded-[28px] border border-[var(--theme-line)] bg-[var(--theme-panel)] shadow-[var(--theme-shadow)]">
        <div className="bg-gradient-to-r from-[#17120f] via-[#2d2119] to-[#4a2e1d] px-6 py-8 text-[var(--theme-on-accent)]">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#f2d1b2]">Email de agendamento</p>
          <h1 className="mt-3 text-3xl font-black">{config.titulo}</h1>
          <p className="mt-2 max-w-2xl text-sm text-[#f3dfce]">{config.descricao}</p>
        </div>

        <div className="space-y-5 px-6 py-7">
          {loading ? <p className="text-sm text-[var(--theme-muted)]">Carregando dados do agendamento...</p> : null}
          {erro ? (
            <div className="rounded-2xl bg-[var(--theme-danger-soft)] px-4 py-3 text-sm font-semibold text-[var(--theme-danger-text)]">
              {erro}
            </div>
          ) : null}
          {sucesso ? (
            <div className="rounded-2xl bg-[var(--theme-success-soft)] px-4 py-3 text-sm font-semibold text-[var(--theme-success-text)]">
              {sucesso}
            </div>
          ) : null}

          {dados ? (
            <>
              <div className="grid gap-4 rounded-[22px] bg-[var(--theme-panel-strong)] p-5 md:grid-cols-2">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">Cliente</p>
                  <p className="mt-2 text-lg font-semibold text-[var(--theme-text)]">{dados.cliente_nome}</p>
                  <p className="text-sm text-[var(--theme-muted)]">{dados.cliente_email ?? "Email nao informado"}</p>
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">Status atual</p>
                  <p className="mt-2 text-lg font-semibold text-[var(--theme-text)]">{labelStatus(dados.status)}</p>
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">Servico</p>
                  <p className="mt-2 text-[var(--theme-text)]">{dados.servico_nome}</p>
                  <p className="text-sm text-[var(--theme-muted)]">{dados.barbeiro_nome}</p>
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">Horario</p>
                  <p className="mt-2 text-[var(--theme-text)]">{formatarDataHora(dados.data_hora_inicio)}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  className="inline-flex min-h-12 items-center justify-center rounded-full bg-[var(--theme-accent)] px-6 text-sm font-bold text-[var(--theme-on-accent)] transition hover:bg-[var(--theme-accent-strong)] disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={submitting}
                  onClick={onAction}
                  type="button"
                >
                  {submitting ? "Processando..." : config.botao}
                </button>

                {mode === "reagendar" ? (
                  <Link
                    className="inline-flex min-h-12 items-center justify-center rounded-full border border-[var(--theme-line-strong)] px-6 text-sm font-bold text-[var(--theme-text)] transition hover:bg-[var(--theme-accent-soft)]"
                    href={linkAgendamento}
                  >
                    Escolher novo horario
                  </Link>
                ) : null}
              </div>
            </>
          ) : null}
        </div>
      </section>
    </main>
  );
}
