import { AgendaSlot } from "@/services/api";
import styles from "./AgendaCell.module.css";

type AgendaCellProps = {
  hora: string;
  profissionalNome: string;
  agendamento?: AgendaSlot;
  disponivel?: boolean;
  isSelected?: boolean;
  onSelect: () => void;
};

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export default function AgendaCell({
  hora,
  profissionalNome,
  agendamento,
  disponivel = true,
  isSelected = false,
  onSelect,
}: AgendaCellProps) {
  const aguardandoPagamento =
    agendamento?.status === "pending_payment" || agendamento?.payment_status === "pending";
  const bloqueado = !disponivel && !agendamento;
  const ocupado = Boolean(agendamento);

  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={bloqueado}
      className={cx(
        styles.cell,
        ocupado && !aguardandoPagamento && styles.cellConfirmado,
        aguardandoPagamento && styles.cellPendingPayment,
        bloqueado && styles.cellIndisponivel,
        !ocupado && !bloqueado && styles.cellLivre,
        isSelected && styles.cellSelected
      )}
      aria-label={`${profissionalNome} as ${hora}`}
    >
      <span className={styles.hour}>{hora}</span>

      {agendamento ? (
        <span className={styles.caption}>{agendamento.cliente}</span>
      ) : (
        <span className={styles.caption}>{bloqueado ? "Indisponivel" : "Livre"}</span>
      )}
    </button>
  );
}
