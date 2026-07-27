"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";

import { PRODUCT_NAME } from "@/lib/brand";
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
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function labelStatus(status: PublicAgendamentoTokenResponse["status"]) {
  const mapa: Record<string, { label: string; color: string }> = {
    pendente:                 { label: "Pendente",                color: "#854d0e" },
    confirmado:               { label: "Confirmado",              color: "#166534" },
    cancelado:                { label: "Cancelado",               color: "#991b1b" },
    reagendamento_solicitado: { label: "Reagendamento solicitado", color: "#6d28d9" },
  };
  return mapa[status] ?? { label: status, color: "#6b7280" };
}

function montarLinkAgendamento(dados: PublicAgendamentoTokenResponse | null) {
  if (!dados) return "/";
  return `/agendar/${dados.estabelecimento_id}`;
}

const modeConfig = {
  confirmar: {
    titulo: "Confirmar presença",
    subtitulo: "Confirme que você comparecerá ao seu horário.",
    botao: "Confirmar presença",
    executar: confirmBookingByToken,
    sucessoMsg: "Presença confirmada! Até logo.",
    accentColor: "#166534",
    accentBg: "#f0fdf4",
    accentText: "#166534",
  },
  cancelar: {
    titulo: "Cancelar agendamento",
    subtitulo: "Não poderá comparecer? Cancele com antecedência.",
    botao: "Cancelar horário",
    executar: cancelBookingByToken,
    sucessoMsg: "Agendamento cancelado.",
    accentColor: "#991b1b",
    accentBg: "#fef2f2",
    accentText: "#991b1b",
  },
  reagendar: {
    titulo: "Reagendar",
    subtitulo: "Solicite o reagendamento e escolha um novo horário.",
    botao: "Solicitar reagendamento",
    executar: requestRescheduleByToken,
    sucessoMsg: "Pedido de reagendamento registrado.",
    accentColor: "#1e3a5f",
    accentBg: "#eaf0f5",
    accentText: "#142a44",
  },
} satisfies Record<BookingActionMode, unknown>;

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
        setErro(err instanceof Error ? err.message : "Não foi possível carregar o agendamento.");
      } finally {
        if (ativo) setLoading(false);
      }
    }
    carregar();
    return () => { ativo = false; };
  }, [token]);

  const config = modeConfig[mode];
  const linkAgendamento = montarLinkAgendamento(dados);
  const status = dados ? labelStatus(dados.status) : null;

  async function onAction() {
    setSubmitting(true);
    setErro(null);
    setSucesso(null);
    try {
      const resposta = await config.executar(token);
      setDados(resposta);
      setSucesso(config.sucessoMsg);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível concluir a ação.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#f6f8fb",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-start",
        padding: "0",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Top brand bar */}
      <div
        style={{
          width: "100%",
          backgroundColor: "#14283f",
          padding: "14px 24px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            backgroundColor: "#1e3a5f",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <CalendarDays size={17} color="#ffffff" aria-hidden="true" />
        </div>
        <span style={{ color: "#ffffff", fontWeight: 700, fontSize: 15, letterSpacing: "0.02em" }}>
          {PRODUCT_NAME}
        </span>
      </div>

      {/* Card */}
      <div
        style={{
          width: "100%",
          maxWidth: 560,
          margin: "40px 16px",
          backgroundColor: "#ffffff",
          borderRadius: 20,
          boxShadow: "0 4px 24px rgba(0,0,0,0.10)",
          overflow: "hidden",
        }}
      >
        {/* Card header */}
        <div
          style={{
            background: "linear-gradient(135deg, #1e3a5f 0%, #122840 100%)",
            padding: "32px 32px 28px",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#d99b3f",
            }}
          >
            Email de agendamento
          </p>
          <h1
            style={{
              margin: "10px 0 6px",
              fontSize: 26,
              fontWeight: 800,
              color: "#ffffff",
              lineHeight: 1.2,
            }}
          >
            {config.titulo}
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: "rgba(255,255,255,0.75)" }}>
            {config.subtitulo}
          </p>
        </div>

        {/* Card body */}
        <div style={{ padding: "28px 32px 32px" }}>

          {/* Loading */}
          {loading && (
            <p style={{ color: "#9a9a9a", fontSize: 14, margin: 0 }}>
              Carregando dados do agendamento...
            </p>
          )}

          {/* Error */}
          {erro && (
            <div
              style={{
                backgroundColor: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: 12,
                padding: "12px 16px",
                marginBottom: 20,
                fontSize: 14,
                color: "#991b1b",
                fontWeight: 500,
              }}
            >
              {erro}
            </div>
          )}

          {/* Success */}
          {sucesso && (
            <div
              style={{
                backgroundColor: config.accentBg,
                border: `1px solid ${config.accentColor}33`,
                borderRadius: 12,
                padding: "12px 16px",
                marginBottom: 20,
                fontSize: 14,
                color: config.accentText,
                fontWeight: 600,
              }}
            >
              ✓ {sucesso}
            </div>
          )}

          {/* Booking details */}
          {dados && (
            <>
              <div
                style={{
                  backgroundColor: "#f0f2f5",
                  borderRadius: 14,
                  padding: "20px 22px",
                  marginBottom: 24,
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "18px 24px",
                }}
              >
                <div>
                  <p style={{ margin: "0 0 4px", fontSize: 10, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "#d99b3f" }}>
                    Cliente
                  </p>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#1a1a1a" }}>
                    {dados.cliente_nome}
                  </p>
                  {dados.cliente_email && (
                    <p style={{ margin: "2px 0 0", fontSize: 12, color: "#6b7280" }}>
                      {dados.cliente_email}
                    </p>
                  )}
                </div>

                <div>
                  <p style={{ margin: "0 0 4px", fontSize: 10, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "#d99b3f" }}>
                    Status
                  </p>
                  <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: status?.color }}>
                    {status?.label}
                  </p>
                </div>

                <div>
                  <p style={{ margin: "0 0 4px", fontSize: 10, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "#d99b3f" }}>
                    Serviço
                  </p>
                  <p style={{ margin: 0, fontSize: 14, fontWeight: 500, color: "#1a1a1a" }}>
                    {dados.servico_nome}
                  </p>
                  <p style={{ margin: "2px 0 0", fontSize: 12, color: "#6b7280" }}>
                    {dados.barbeiro_nome}
                  </p>
                </div>

                <div>
                  <p style={{ margin: "0 0 4px", fontSize: 10, fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "#d99b3f" }}>
                    Horário
                  </p>
                  <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: "#1a1a1a", lineHeight: 1.4 }}>
                    {formatarDataHora(dados.data_hora_inicio)}
                  </p>
                </div>
              </div>

              {/* Actions */}
              {!sucesso && (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <button
                    onClick={onAction}
                    disabled={submitting}
                    style={{
                      width: "100%",
                      padding: "14px 20px",
                      borderRadius: 12,
                      border: "none",
                      backgroundColor: config.accentColor,
                      color: "#ffffff",
                      fontSize: 15,
                      fontWeight: 700,
                      cursor: submitting ? "not-allowed" : "pointer",
                      opacity: submitting ? 0.6 : 1,
                      transition: "opacity 0.15s",
                    }}
                    type="button"
                  >
                    {submitting ? "Processando..." : config.botao}
                  </button>

                  {mode === "reagendar" && (
                    <Link
                      href={linkAgendamento}
                      style={{
                        display: "block",
                        textAlign: "center",
                        padding: "13px 20px",
                        borderRadius: 12,
                        border: "1.5px solid #e5e9ee",
                        backgroundColor: "transparent",
                        color: "#142a44",
                        fontSize: 14,
                        fontWeight: 600,
                        textDecoration: "none",
                      }}
                    >
                      Escolher novo horário →
                    </Link>
                  )}
                </div>
              )}

              {sucesso && (
                <Link
                  href={linkAgendamento}
                  style={{
                    display: "block",
                    textAlign: "center",
                    padding: "13px 20px",
                    borderRadius: 12,
                    border: "1.5px solid #e5e9ee",
                    backgroundColor: "transparent",
                    color: "#142a44",
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  Voltar para o site do estabelecimento →
                </Link>
              )}
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <p style={{ fontSize: 12, color: "#9a9a9a", marginBottom: 32 }}>
        Agendamento por {PRODUCT_NAME}
      </p>
    </div>
  );
}
