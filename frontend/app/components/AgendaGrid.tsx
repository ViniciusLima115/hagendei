import AgendaCell from "./AgendaCell";
import { AgendaDiaResponse, AgendaSlot } from "@/services/api";

export type SelectedAgendamento = {
  hora: string;
  barbeiroId: number;
  barbeiroNome: string;
  agendamento?: AgendaSlot;
};

type AgendaGridProps = {
  data: AgendaDiaResponse;
  selectedKey?: string;
  onSelect: (item: SelectedAgendamento) => void;
};

export default function AgendaGrid({
  data,
  selectedKey,
  onSelect,
}: AgendaGridProps) {
  return (
    <div className="glass-panel overflow-hidden rounded-2xl">
      <div
        className="grid gap-2 overflow-auto p-4"
        style={{
          gridTemplateColumns: `110px repeat(${data.barbeiros.length}, minmax(210px, 1fr))`,
        }}
      >
        <div className="sticky left-0 top-0 z-20 rounded-lg bg-[var(--surface)] px-2 py-3 text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Horário
        </div>
        {data.barbeiros.map((b) => (
          <div
            key={b.id}
            className="rounded-lg border border-[var(--line)] bg-[var(--surface)] px-2 py-3 text-center text-sm font-bold uppercase tracking-wide text-[var(--foreground)]"
          >
            {b.nome}
          </div>
        ))}

        {data.horarios.map((hora) => (
          <div key={hora} className="contents">
            <div className="sticky left-0 z-10 rounded-lg border border-[var(--line)] bg-[var(--surface)] px-2 py-3 text-sm font-semibold text-zinc-700">
              {hora}
            </div>

            {data.barbeiros.map((b) => {
              const ag = b.agendamentos.find((a) => a.hora === hora);
              const key = `${b.id}-${hora}`;

              return (
                <AgendaCell
                  key={key}
                  hora={hora}
                  barbeiroNome={b.nome}
                  agendamento={ag}
                  isSelected={selectedKey === key}
                  onSelect={() =>
                    onSelect({
                      hora,
                      barbeiroId: b.id,
                      barbeiroNome: b.nome,
                      agendamento: ag,
                    })
                  }
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
