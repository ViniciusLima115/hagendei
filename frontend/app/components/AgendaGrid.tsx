import AgendaCell from "./AgendaCell";
import { AgendaDiaResponse, AgendaSlot } from "@/services/api";
import styles from "./AgendaGrid.module.css";

export type SelectedAgendamento = {
  hora: string;
  profissionalId: number;
  profissionalNome: string;
  agendamento?: AgendaSlot;
};

type AgendaGridProps = {
  data: AgendaDiaResponse;
  selectedKey?: string;
  onSelect: (item: SelectedAgendamento) => void;
};

export default function AgendaGrid({ data, selectedKey, onSelect }: AgendaGridProps) {
  return (
    <div className={styles.grid}>
      {data.barbeiros.map((barbeiro) => (
        <section key={barbeiro.id} className={styles.column}>
          <div className={styles.columnHeader}>
            <h3 className={styles.columnTitle}>{barbeiro.nome}</h3>
            <p className={styles.columnMeta}>{barbeiro.horarios.length} slots validos no dia</p>
          </div>

          <div className={styles.slotGrid}>
            {data.horarios.map((hora) => {
              const agendamento = barbeiro.agendamentos.find((item) => item.hora === hora);
              const disponivel = barbeiro.horarios.includes(hora);
              const key = `${barbeiro.id}-${hora}`;

              return (
                <AgendaCell
                  key={key}
                  hora={hora}
                  profissionalNome={barbeiro.nome}
                  agendamento={agendamento}
                  disponivel={disponivel}
                  isSelected={selectedKey === key}
                  onSelect={() => {
                    if (!disponivel && !agendamento) return;
                    onSelect({
                      hora,
                      profissionalId: barbeiro.id,
                      profissionalNome: barbeiro.nome,
                      agendamento,
                    });
                  }}
                />
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
