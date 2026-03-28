"use client";

import Link from "next/link";
import { ArrowLeft, Check, Minus } from "lucide-react";
import styles from "./page.module.css";

type Feature = {
  label: string;
  basico: boolean;
  premium: boolean;
};

const FEATURES: Feature[] = [
  { label: "Profissionais ativos", basico: false, premium: false },
  { label: "Agendamentos ilimitados", basico: true, premium: true },
  { label: "Dashboard financeiro", basico: false, premium: true },
  { label: "Análise de clientes", basico: false, premium: true },
  { label: "Ranking de serviços", basico: false, premium: true },
  { label: "Suporte prioritário", basico: false, premium: true },
];

function FeatureIcon({ has }: { has: boolean }) {
  if (has) {
    return <Check size={16} className={`${styles.featureIcon} ${styles.featureIconCheck}`} />;
  }
  return <Minus size={16} className={`${styles.featureIcon} ${styles.featureIconMissing}`} />;
}

export default function UpgradePage() {
  return (
    <div className={styles.page}>
      <div className={styles.shell}>
        <Link href="/gestao" className={styles.backLink}>
          <ArrowLeft size={14} />
          Voltar para gestão
        </Link>

        <div className={styles.header}>
          <p className={styles.eyebrow}>Planos</p>
          <h1 className={styles.title}>Escolha seu plano</h1>
          <p className={styles.subtitle}>
            Comece grátis e faça upgrade quando precisar de mais recursos.
          </p>
        </div>

        <div className={styles.plansGrid}>
          {/* Plano Básico */}
          <div className={styles.planCard}>
            <div className={styles.planCardHeader}>
              <div className={styles.planBadgeRow}>
                <h2 className={styles.planName}>Básico</h2>
              </div>
              <p className={styles.planPrice}>
                Grátis
              </p>
              <p className={styles.planDescription}>
                Para quem está começando e precisa do essencial.
              </p>
            </div>

            <ul className={styles.featureList}>
              <li className={styles.featureItem}>
                <FeatureIcon has={true} />
                1 profissional ativo
              </li>
              {FEATURES.slice(1).map((f) => (
                <li key={f.label} className={styles.featureItem}>
                  <FeatureIcon has={f.basico} />
                  {f.label}
                </li>
              ))}
            </ul>

            <button disabled className={styles.ctaButton + " " + styles.ctaButtonSecondary}>
              Plano atual
            </button>
          </div>

          {/* Plano Premium */}
          <div className={`${styles.planCard} ${styles.planCardHighlight}`}>
            <div className={styles.planCardHeader}>
              <div className={styles.planBadgeRow}>
                <h2 className={styles.planName}>Premium</h2>
                <span className={styles.planBadge}>Recomendado</span>
              </div>
              <p className={styles.planPrice}>
                R$ 49<span className={styles.planPriceSub}>/mês</span>
              </p>
              <p className={styles.planDescription}>
                Para estabelecimentos que querem crescer com dados e mais equipe.
              </p>
            </div>

            <ul className={styles.featureList}>
              <li className={styles.featureItem}>
                <FeatureIcon has={true} />
                Até 3 profissionais ativos
              </li>
              {FEATURES.slice(1).map((f) => (
                <li key={f.label} className={styles.featureItem}>
                  <FeatureIcon has={f.premium} />
                  {f.label}
                </li>
              ))}
            </ul>

            <button disabled className={styles.ctaButton + " " + styles.ctaButtonPrimary}>
              Em breve
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
