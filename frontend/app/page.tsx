import Link from "next/link";

export default function Home() {
  return (
    <main className="px-4 py-10 md:px-8">
      <section className="glass-panel fade-up mx-auto grid max-w-5xl gap-8 rounded-3xl p-8 md:grid-cols-[1.2fr_0.8fr] md:p-10">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            Gestão Profissional
          </p>
          <h1 className="mt-3 text-4xl font-black uppercase tracking-tight text-[var(--foreground)] md:text-5xl">
            Painel da Barbearia
          </h1>
          <p className="mt-3 max-w-xl text-sm text-zinc-600 md:text-base">
            Controle agenda, visualize ocupação e acompanhe os atendimentos em tempo real com uma interface clara para operação diária.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/agenda"
              className="inline-flex items-center rounded-xl bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90"
            >
              Abrir Agenda
            </Link>
            <Link
              href="/gestao"
              className="inline-flex items-center rounded-xl border border-[var(--line-strong)] bg-[var(--surface)] px-5 py-3 text-sm font-semibold transition hover:bg-[var(--surface-muted)]"
            >
              Abrir Gestão
            </Link>
          </div>
        </div>

        <div className="rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Recursos
          </p>
          <ul className="mt-3 space-y-3 text-sm text-zinc-700">
            <li>Grade por profissional e horário</li>
            <li>Detalhes de cada agendamento por clique</li>
            <li>Filtros de data para visão diária</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
