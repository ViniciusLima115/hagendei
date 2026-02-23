"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AgendaGrid, { SelectedAgendamento } from "../components/AgendaGrid";
import { AgendaDiaResponse, getAgendaDia } from "@/services/api";

export default function AgendaPage() {
  const [selectedDate, setSelectedDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [data, setData] = useState<AgendaDiaResponse | null>(null);
  const [selected, setSelected] = useState<SelectedAgendamento | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const carregarAgenda = async () => {
      setLoading(true);
      setError(null);

      try {
        const resposta = await getAgendaDia(selectedDate);
        setData(resposta);
        setSelected(null);
      } catch (err) {
        setData(null);
        setSelected(null);
        setError("Falha ao buscar agenda. Confirme se o backend está acessível em http://34.121.162.107.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    carregarAgenda();
  }, [selectedDate]);

  const selectedKey = selected ? `${selected.barbeiroId}-${selected.hora}` : undefined;
  const totalSlots = data ? data.horarios.length * data.barbeiros.length : 0;
  const totalOcupados = data
    ? data.barbeiros.reduce((acc, b) => acc + b.agendamentos.length, 0)
    : 0;
  const totalLivres = Math.max(totalSlots - totalOcupados, 0);
  const taxaOcupacao = totalSlots > 0 ? Math.round((totalOcupados / totalSlots) * 100) : 0;

  return (
    <div className="px-4 py-6 md:px-8 md:py-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <section className="glass-panel fade-up rounded-2xl p-6 md:p-8">
          <div className="flex flex-wrap items-end justify-between gap-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                Painel Operacional
              </p>
              <h1 className="mt-2 text-3xl font-black uppercase tracking-tight md:text-4xl">
                Agenda da Barbearia
              </h1>
              <p className="mt-2 text-sm text-zinc-600">
                Visualize horários, ocupação diária e detalhes de atendimento em um só lugar.
              </p>
            </div>

            <div className="min-w-[220px] space-y-2 text-sm">
              <span className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Data de consulta
              </span>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="w-full rounded-xl border border-[var(--line-strong)] bg-[var(--surface)] px-3 py-2 font-semibold outline-none transition focus:border-[var(--accent)]"
              />
              <Link
                href="/gestao"
                className="inline-flex rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-semibold"
              >
                Ir para Gestão
              </Link>
            </div>
          </div>
        </section>

        <section className="grid gap-3 md:grid-cols-4">
          <article className="glass-panel fade-up rounded-xl p-4" style={{ animationDelay: "0.03s" }}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
              Slots do dia
            </p>
            <p className="mt-1 text-2xl font-black">{totalSlots}</p>
          </article>
          <article className="glass-panel fade-up rounded-xl p-4" style={{ animationDelay: "0.07s" }}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
              Ocupados
            </p>
            <p className="mt-1 text-2xl font-black text-[var(--ok)]">{totalOcupados}</p>
          </article>
          <article className="glass-panel fade-up rounded-xl p-4" style={{ animationDelay: "0.11s" }}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
              Livres
            </p>
            <p className="mt-1 text-2xl font-black">{totalLivres}</p>
          </article>
          <article className="glass-panel fade-up rounded-xl p-4" style={{ animationDelay: "0.15s" }}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500">
              Ocupação
            </p>
            <p className="mt-1 text-2xl font-black">{taxaOcupacao}%</p>
          </article>
        </section>

        {loading && (
          <div className="glass-panel fade-up rounded-xl p-4 text-sm text-zinc-600">
            Carregando agenda...
          </div>
        )}
        {error && (
          <div className="fade-up rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-[var(--danger)]">
            {error}
          </div>
        )}

        {!loading && !error && data && (
          <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
            <div className="fade-up" style={{ animationDelay: "0.18s" }}>
              <AgendaGrid
                data={data}
                selectedKey={selectedKey}
                onSelect={setSelected}
              />
            </div>

            <aside className="glass-panel fade-up h-fit rounded-2xl p-5" style={{ animationDelay: "0.22s" }}>
              <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-zinc-500">
                Detalhes do Slot
              </h2>

              {!selected && (
                <p className="mt-3 text-sm text-zinc-600">
                  Selecione um horário na grade para abrir os dados completos do atendimento.
                </p>
              )}

              {selected && (
                <div className="mt-4 space-y-3 text-sm">
                  <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Profissional</p>
                    <p className="mt-1 font-bold">{selected.barbeiroNome}</p>
                  </div>
                  <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Horário</p>
                    <p className="mt-1 font-bold">{selected.hora}</p>
                  </div>
                </div>
              )}

              {selected && !selected.agendamento && (
                <div className="mt-4 rounded-xl border border-[var(--line)] bg-[var(--surface)] p-3 text-sm">
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Status</p>
                  <p className="mt-1 font-bold text-zinc-700">Livre para novo agendamento</p>
                </div>
              )}

              {selected?.agendamento && (
                <div className="mt-4 space-y-2 rounded-xl border border-[var(--line)] bg-[var(--surface)] p-3 text-sm">
                  <p><strong>Status:</strong> {selected.agendamento.status ?? "Agendado"}</p>
                  <p><strong>Cliente:</strong> {selected.agendamento.cliente}</p>
                  <p><strong>Telefone:</strong> {selected.agendamento.telefone ?? "Não informado"}</p>
                  <p><strong>Serviço:</strong> {selected.agendamento.servico}</p>
                  <p><strong>Início:</strong> {selected.agendamento.inicio ?? selected.hora}</p>
                  <p><strong>Fim:</strong> {selected.agendamento.fim ?? "Não informado"}</p>
                </div>
              )}
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}
