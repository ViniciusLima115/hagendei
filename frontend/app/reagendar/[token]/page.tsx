"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import {
  getBookingByToken,
  lookupPublicBarbershopById,
  rescheduleBookingByToken,
  PublicAgendamentoTokenResponse,
  PublicLookupResponse,
} from "@/services/api";

function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

function formatarDataHora(valor: string) {
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor;
  return data.toLocaleString("pt-BR", { dateStyle: "full", timeStyle: "short" });
}

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export default function ReagendarPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";

  const [loadingBooking, setLoadingBooking] = useState(true);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [booking, setBooking] = useState<PublicAgendamentoTokenResponse | null>(null);
  const [lookup, setLookup] = useState<PublicLookupResponse | null>(null);

  const [today] = useState(() => hojeISO());
  const [data, setData] = useState(() => hojeISO());
  const [barbeiroId, setBarbeiroId] = useState<number | null>(null);
  const [servicoId, setServicoId] = useState<number | null>(null);
  const [horaInicio, setHoraInicio] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let ativo = true;

    async function carregar() {
      setLoadingBooking(true);
      setErro(null);
      try {
        const b = await getBookingByToken(token);
        if (!ativo) return;
        setBooking(b);
        setBarbeiroId(b.barbeiro_id);
        setServicoId(b.servico_id);
        const dataExistente = b.data_hora_inicio.slice(0, 10);
        setData(dataExistente >= hojeISO() ? dataExistente : hojeISO());
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Nao foi possivel carregar o agendamento.");
      } finally {
        if (ativo) setLoadingBooking(false);
      }
    }

    carregar();
    return () => {
      ativo = false;
    };
  }, [token]);

  useEffect(() => {
    if (!booking || !barbeiroId || !servicoId || !data) return;
    let ativo = true;

    async function carregarSlots() {
      setLoadingSlots(true);
      try {
        const resultado = await lookupPublicBarbershopById({
          barbearia_id: booking!.barbearia_id,
          data,
          barbeiro_id: barbeiroId!,
          servico_id: servicoId!,
        });
        if (!ativo) return;
        setLookup(resultado);
        setHoraInicio((atual) => {
          if (!atual) return null;
          return resultado.horarios_grade.some((s) => s.hora === atual && s.disponivel)
            ? atual
            : null;
        });
      } catch {
        if (!ativo) return;
      } finally {
        if (ativo) setLoadingSlots(false);
      }
    }

    carregarSlots();
    return () => {
      ativo = false;
    };
  }, [booking, barbeiroId, servicoId, data]);

  async function onSubmit() {
    if (!horaInicio) {
      setErro("Selecione um horario disponivel.");
      return;
    }
    setSubmitting(true);
    setErro(null);
    setSucesso(null);
    try {
      const dataHoraInicio = `${data}T${horaInicio}:00`;
      const atualizado = await rescheduleBookingByToken(token, dataHoraInicio);
      setBooking(atualizado);
      setSucesso("Agendamento reagendado com sucesso!");
      setHoraInicio(null);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Nao foi possivel reagendar.");
    } finally {
      setSubmitting(false);
    }
  }

  const linkBarbearia = booking?.slug
    ? `/${booking.slug}`
    : booking
      ? `/agendar/${booking.barbearia_id}`
      : "/";

  if (loadingBooking) {
    return (
      <main className="min-h-screen bg-[var(--theme-canvas)] px-4 py-10">
        <div className="mx-auto max-w-3xl rounded-[28px] border border-[var(--theme-line)] bg-[var(--theme-panel)] p-8 shadow-[var(--theme-shadow)]">
          <p className="text-sm text-[var(--theme-muted)]">Carregando agendamento...</p>
        </div>
      </main>
    );
  }

  if (!booking) {
    return (
      <main className="min-h-screen bg-[var(--theme-canvas)] px-4 py-10">
        <div className="mx-auto max-w-3xl rounded-[28px] border border-[var(--theme-line)] bg-[var(--theme-panel)] p-8 shadow-[var(--theme-shadow)]">
          <p className="text-sm text-[var(--theme-danger-text)]">
            {erro ?? "Agendamento nao encontrado."}
          </p>
        </div>
      </main>
    );
  }

  const cancelado = booking.status === "cancelado";

  return (
    <main className="min-h-screen bg-[var(--theme-canvas)] px-4 py-10">
      <section className="mx-auto max-w-3xl overflow-hidden rounded-[28px] border border-[var(--theme-line)] bg-[var(--theme-panel)] shadow-[var(--theme-shadow)]">
        <div className="bg-gradient-to-r from-[#17120f] via-[#2d2119] to-[#4a2e1d] px-6 py-8 text-[var(--theme-on-accent)]">
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[#f2d1b2]">
            Email de agendamento
          </p>
          <h1 className="mt-3 text-3xl font-black">Escolha um novo horario</h1>
          <p className="mt-2 text-sm text-[#f3dfce]">
            Selecione a data e o horario para seu reagendamento.
          </p>
        </div>

        <div className="space-y-6 px-6 py-7">
          {/* Booking details */}
          <div className="grid gap-4 rounded-[22px] bg-[var(--theme-panel-strong)] p-5 md:grid-cols-2">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">
                Cliente
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--theme-text)]">
                {booking.cliente_nome}
              </p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">
                Horario atual
              </p>
              <p className="mt-2 text-[var(--theme-text)]">
                {formatarDataHora(booking.data_hora_inicio)}
              </p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">
                Servico
              </p>
              <p className="mt-2 text-[var(--theme-text)]">{booking.servico_nome}</p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">
                Barbeiro
              </p>
              <p className="mt-2 text-[var(--theme-text)]">{booking.barbeiro_nome}</p>
            </div>
          </div>

          {sucesso ? (
            <div className="rounded-2xl bg-[var(--theme-success-soft)] px-4 py-3 text-sm font-semibold text-[var(--theme-success-text)]">
              {sucesso}
            </div>
          ) : null}

          {erro ? (
            <div className="rounded-2xl bg-[var(--theme-danger-soft)] px-4 py-3 text-sm font-semibold text-[var(--theme-danger-text)]">
              {erro}
            </div>
          ) : null}

          {cancelado ? (
            <div className="rounded-2xl bg-[var(--theme-danger-soft)] px-4 py-3 text-sm font-semibold text-[var(--theme-danger-text)]">
              Este agendamento foi cancelado e nao pode ser reagendado.
            </div>
          ) : sucesso ? null : (
            <>
              {/* Selectors */}
              {lookup ? (
                <div className="grid gap-4 md:grid-cols-3">
                  <label className="flex flex-col gap-1">
                    <span className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">
                      Barbeiro
                    </span>
                    <select
                      className="rounded-xl border border-[var(--theme-line)] bg-[var(--theme-panel)] px-3 py-2 text-sm text-[var(--theme-text)]"
                      value={barbeiroId ?? ""}
                      onChange={(e) => {
                        setBarbeiroId(Number(e.target.value));
                        setHoraInicio(null);
                      }}
                    >
                      {lookup.barbeiros.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.nome}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-1">
                    <span className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">
                      Servico
                    </span>
                    <select
                      className="rounded-xl border border-[var(--theme-line)] bg-[var(--theme-panel)] px-3 py-2 text-sm text-[var(--theme-text)]"
                      value={servicoId ?? ""}
                      onChange={(e) => {
                        setServicoId(Number(e.target.value));
                        setHoraInicio(null);
                      }}
                    >
                      {lookup.servicos.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.nome}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="flex flex-col gap-1">
                    <span className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--theme-accent-strong)]">
                      Data
                    </span>
                    <input
                      type="date"
                      min={today}
                      value={data}
                      onChange={(e) => {
                        setData(e.target.value);
                        setHoraInicio(null);
                      }}
                      className="rounded-xl border border-[var(--theme-line)] bg-[var(--theme-panel)] px-3 py-2 text-sm text-[var(--theme-text)]"
                    />
                  </label>
                </div>
              ) : null}

              {/* Time slots */}
              {loadingSlots ? (
                <p className="text-sm text-[var(--theme-muted)]">Carregando horarios...</p>
              ) : lookup && lookup.horarios_grade.length > 0 ? (
                <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
                  {lookup.horarios_grade.map((slot) => (
                    <button
                      key={slot.hora}
                      type="button"
                      disabled={!slot.disponivel}
                      onClick={() => setHoraInicio(slot.hora)}
                      className={cx(
                        "flex flex-col items-center rounded-2xl border px-2 py-3 text-xs font-bold transition",
                        slot.disponivel
                          ? horaInicio === slot.hora
                            ? "border-[var(--theme-accent)] bg-[var(--theme-accent)] text-[var(--theme-on-accent)]"
                            : "border-[var(--theme-line)] bg-[var(--theme-panel)] text-[var(--theme-text)] hover:border-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)]"
                          : "cursor-not-allowed border-[var(--theme-line)] bg-[var(--theme-panel-strong)] text-[var(--theme-muted)] opacity-50",
                      )}
                    >
                      <span>{slot.hora}</span>
                      <span className="mt-1 font-normal opacity-70">
                        {slot.disponivel ? "Livre" : "Indisp."}
                      </span>
                    </button>
                  ))}
                </div>
              ) : lookup ? (
                <p className="text-sm text-[var(--theme-muted)]">
                  Nenhum horario disponivel nesta data.
                </p>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  disabled={submitting || !horaInicio}
                  onClick={onSubmit}
                  className="inline-flex min-h-12 items-center justify-center rounded-full bg-[var(--theme-accent)] px-6 text-sm font-bold text-[var(--theme-on-accent)] transition hover:bg-[var(--theme-accent-strong)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Reagendando..." : "Confirmar novo horario"}
                </button>
              </div>
            </>
          )}

          {(sucesso || cancelado) ? (
            <Link
              href={linkBarbearia}
              className="inline-flex min-h-12 items-center justify-center rounded-full border border-[var(--theme-line-strong)] px-6 text-sm font-bold text-[var(--theme-text)] transition hover:bg-[var(--theme-accent-soft)]"
            >
              Voltar para o site da barbearia
            </Link>
          ) : null}
        </div>
      </section>
    </main>
  );
}
