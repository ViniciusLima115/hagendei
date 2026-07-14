"use client";

import { useEffect, useState } from "react";
import { BarChart2, CalendarCheck2, DollarSign, TrendingUp } from "lucide-react";
import { useAuthSession } from "@/services/auth";
import { getDashboardAnalise, type AnaliseResponse } from "@/services/api";
import styles from "./page.module.css";

const brl = (v: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

export default function AnaliseTab() {
  const session = useAuthSession();
  const tenantId = session?.tenantId ?? "";

  const [data, setData] = useState<AnaliseResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;
    getDashboardAnalise(tenantId)
      .then(setData)
      .catch(() => setError("Erro ao carregar análise."))
      .finally(() => setLoading(false));
  }, [tenantId]);

  if (loading) {
    return (
      <div className={styles.loadingState}>
        <div className={styles.loadingPulse} />
        <p style={{ color: "var(--ink-muted)" }}>Carregando análise…</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={styles.loadingState}>
        <p style={{ color: "var(--danger)" }}>{error ?? "Erro ao carregar análise."}</p>
      </div>
    );
  }

  const maxSemana = Math.max(...data.semana.map((d) => d.clientes), 1);
  const maxServico = data.servicos[0]?.total ?? 1;

  return (
    <div style={{ marginTop: "20px" }}>
      {/* Bloco 1 — Resumo do mês */}
      <div className={styles.statsGrid}>
        <article className={styles.statCard}>
          <div className={styles.statIcon}><CalendarCheck2 size={22} /></div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Agendamentos</span>
            <strong className={styles.statValue}>{data.resumo.agendamentos}</strong>
            <span className={styles.statHelper}>no mês atual</span>
          </div>
        </article>

        <article className={styles.statCard}>
          <div className={styles.statIcon}><DollarSign size={22} /></div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Faturamento</span>
            <strong className={styles.statValue}>{brl(data.resumo.faturamento)}</strong>
            <span className={styles.statHelper}>no mês atual</span>
          </div>
        </article>

        <article className={styles.statCard}>
          <div className={styles.statIcon}><TrendingUp size={22} /></div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Ticket médio</span>
            <strong className={styles.statValue}>{brl(data.resumo.ticket_medio)}</strong>
            <span className={styles.statHelper}>por agendamento</span>
          </div>
        </article>

        <article className={styles.statCard}>
          <div className={styles.statIcon}><BarChart2 size={22} /></div>
          <div className={styles.statContent}>
            <span className={styles.statLabel}>Taxa de ocupação</span>
            <strong className={styles.statValue}>{data.resumo.ocupacao}%</strong>
            <span className={styles.statHelper}>da agenda preenchida</span>
          </div>
        </article>
      </div>

      {/* Linha 2: Bloco 2 + Bloco 3 */}
      <div className={styles.analiseGrid3Col}>
        {/* Bloco 2 — Movimento da semana */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Movimento da semana</h2>
          <div className={styles.weekBarList}>
            {data.semana.map((item) => {
              const isPeak = item.clientes === maxSemana;
              return (
                <div key={item.dia} className={styles.weekBarItem}>
                  <span className={isPeak ? `${styles.weekBarLabel} ${styles.weekBarLabelPeak}` : styles.weekBarLabel}>
                    {item.dia}
                  </span>
                  <div className={styles.weekBarTrack}>
                    <div
                      className={isPeak ? `${styles.weekBarFill} ${styles.weekBarFillPeak}` : styles.weekBarFill}
                      style={{ width: `${(item.clientes / maxSemana) * 100}%` }}
                    />
                  </div>
                  <span className={isPeak ? `${styles.weekBarCount} ${styles.weekBarCountPeak}` : styles.weekBarCount}>
                    {item.clientes}
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        {/* Bloco 3 — Horários mais cheios */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Horários mais cheios</h2>
          <div className={styles.rankList}>
            {data.horarios.map((item, i) => {
              const isTop = i === 0;
              return (
                <div key={item.hora} className={isTop ? `${styles.rankItem} ${styles.rankItemTop}` : styles.rankItem}>
                  <span className={isTop ? `${styles.rankPos} ${styles.rankPosTop}` : styles.rankPos}>
                    #{i + 1}
                  </span>
                  <span className={styles.rankLabel}>{item.hora}</span>
                  <span className={isTop ? `${styles.rankCount} ${styles.rankCountTop}` : styles.rankCount}>
                    {item.atendimentos} atend.
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* Linha 3: Bloco 4 + Bloco 5 */}
      <div className={styles.analiseGrid2Col}>
        {/* Bloco 4 — Serviços mais vendidos */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Serviços mais vendidos</h2>
          <div className={styles.servicosList}>
            {data.servicos.map((s) => (
              <div key={s.nome} className={styles.servicoItem}>
                <div className={styles.servicoHeader}>
                  <span className={styles.servicoNome}>{s.nome}</span>
                  <span className={styles.servicoVendas}>{s.total}×</span>
                </div>
                <div className={styles.progressTrack}>
                  <div
                    className={styles.progressBar}
                    style={{ width: `${(s.total / maxServico) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Bloco 5 — Clientes & Retenção */}
        <section className={styles.panel}>
          <h2 className={styles.panelTitle}>Clientes & Retenção</h2>
          <div className={styles.clienteStats} style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{data.clientes.novos}</strong>
              <span className={styles.clienteStatLabel}>Novos</span>
            </div>
            <div className={styles.clienteStatItem}>
              <strong className={styles.clienteStatValue}>{data.clientes.recorrentes}</strong>
              <span className={styles.clienteStatLabel}>Recorrentes</span>
            </div>
          </div>
          <hr className={styles.metricDivider} />
          <div className={styles.clienteStats} style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
            <div className={`${styles.clienteStatItem} ${styles.clienteStatItemDanger}`}>
              <strong className={`${styles.clienteStatValue} ${styles.clienteStatValueDanger}`}>
                {data.clientes.cancelamentos}
              </strong>
              <span className={`${styles.clienteStatLabel} ${styles.clienteStatLabelDanger}`}>
                Cancelamentos
              </span>
            </div>
            <div className={`${styles.clienteStatItem} ${styles.clienteStatItemDanger}`}>
              <strong className={`${styles.clienteStatValue} ${styles.clienteStatValueDanger}`}>
                {data.clientes.no_show}
              </strong>
              <span className={`${styles.clienteStatLabel} ${styles.clienteStatLabelDanger}`}>
                Faltas (no-show)
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
