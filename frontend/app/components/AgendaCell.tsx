import { AgendaSlot } from "@/services/api";

type AgendaCellProps = {
  hora: string;
  barbeiroNome: string;
  agendamento?: AgendaSlot;
  isSelected?: boolean;
  onSelect: () => void;
};

export default function AgendaCell({
  hora,
  barbeiroNome,
  agendamento,
  isSelected = false,
  onSelect,
}: AgendaCellProps) {
  const ocupado = Boolean(agendamento);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        "h-24 w-full rounded-xl border p-3 text-left transition-all duration-200",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-800",
        ocupado
          ? "border-[var(--line-strong)] bg-[var(--surface-muted)] hover:-translate-y-0.5 hover:shadow-md"
          : "border-[var(--line)] bg-[var(--surface)] hover:-translate-y-0.5 hover:border-[var(--line-strong)]",
        isSelected ? "ring-2 ring-[var(--accent)]" : "",
      ].join(" ")}
      aria-label={`${barbeiroNome} às ${hora}`}
    >
      {ocupado ? (
        <div className="flex h-full flex-col justify-between">
          <p className="truncate text-sm font-semibold text-[var(--foreground)]">
            {agendamento?.cliente}
          </p>
          <p className="truncate text-xs text-zinc-600">{agendamento?.servico}</p>
          <p className="text-xs font-semibold uppercase tracking-wide text-[var(--ok)]">
            Ocupado
          </p>
        </div>
      ) : (
        <div className="flex h-full items-end">
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Livre</p>
        </div>
      )}
    </button>
  );
}
