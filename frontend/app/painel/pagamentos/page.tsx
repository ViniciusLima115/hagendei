"use client";

import { FormEvent, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  CreditCard,
  Landmark,
  Plug,
  QrCode,
  RefreshCw,
  Save,
  ShieldCheck,
  Unplug,
  Wallet,
} from "lucide-react";

import {
  PaymentAccountStatus,
  connectMercadoPago,
  disconnectMercadoPago,
  getMercadoPagoStatus,
  updateMercadoPagoSettings,
} from "@/services/api";
import { useAuthSession } from "@/services/auth";
import styles from "./page.module.css";

type AdvancePaymentType = "full" | "signal";

function clampHoldMinutes(value: number): number {
  if (!Number.isFinite(value)) return 10;
  return Math.max(5, Math.min(60, Math.round(value)));
}

function formatDate(value?: string | null): string {
  if (!value) return "Ainda nao registrada";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Ainda nao registrada";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function statusLabel(status?: string): string {
  if (status === "connected") return "Mercado Pago conectado";
  if (status === "expired") return "Mercado Pago expirado";
  if (status === "error") return "Mercado Pago com erro";
  return "Mercado Pago nao conectado";
}

function providerLabel(provider?: string): string {
  if (provider === "mercado_pago") return "Mercado Pago";
  return "Mercado Pago";
}

function PaymentsPanelContent() {
  const session = useAuthSession();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [account, setAccount] = useState<PaymentAccountStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState<"connect" | "disconnect" | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [paymentRequired, setPaymentRequired] = useState(false);
  const [holdMinutes, setHoldMinutes] = useState(10);
  const [advancePaymentType, setAdvancePaymentType] = useState<AdvancePaymentType>("full");
  const [advancePaymentAmount, setAdvancePaymentAmount] = useState("");

  const connected = Boolean(account?.connected);
  const receivingStatus = connected ? "ativo" : "inativo";

  const accountHint = useMemo(() => {
    if (!connected) return "Nenhuma conta autorizada";
    return (
      account?.provider_account_email_masked ||
      account?.external_account_email_masked ||
      account?.provider_account_id_masked ||
      account?.external_user_id_masked ||
      "Conta autorizada"
    );
  }, [account, connected]);

  const syncForm = useCallback((status: PaymentAccountStatus) => {
    setAccount(status);
    setPaymentRequired(Boolean(status.payment_required_default));
    setHoldMinutes(clampHoldMinutes(status.checkout_hold_minutes ?? 10));
    setAdvancePaymentType(status.advance_payment_type === "signal" ? "signal" : "full");
    setAdvancePaymentAmount(
      status.advance_payment_amount !== undefined && status.advance_payment_amount !== null
        ? String(status.advance_payment_amount)
        : "",
    );
  }, []);

  const loadStatus = useCallback(async () => {
    if (!session?.accessToken) return;
    setLoading(true);
    try {
      const status = await getMercadoPagoStatus();
      syncForm(status);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar pagamentos.");
    } finally {
      setLoading(false);
    }
  }, [session?.accessToken, syncForm]);

  useEffect(() => {
    if (session?.tenantId === "admin") router.replace("/admin");
  }, [router, session?.tenantId]);

  useEffect(() => {
    const status = searchParams.get("status");
    if (status === "connected") {
      setSuccess("Mercado Pago conectado com sucesso.");
      router.replace("/painel/pagamentos");
    } else if (status === "error") {
      setError("Nao foi possivel conectar a conta Mercado Pago.");
      router.replace("/painel/pagamentos");
    }
  }, [router, searchParams]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  function clearMessages() {
    setSuccess(null);
    setError(null);
  }

  async function handleConnect() {
    clearMessages();
    setActionLoading("connect");
    try {
      const response = await connectMercadoPago();
      window.location.href = response.authorization_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao iniciar conexao com Mercado Pago.");
      setActionLoading(null);
    }
  }

  async function handleDisconnect() {
    clearMessages();
    const confirmed = window.confirm("Desconectar o Mercado Pago vai impedir novos pagamentos online ate reconectar.");
    if (!confirmed) return;

    setActionLoading("disconnect");
    try {
      const status = await disconnectMercadoPago();
      syncForm(status);
      setSuccess("Mercado Pago desconectado.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao desconectar Mercado Pago.");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleSaveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearMessages();

    const normalizedHoldMinutes = clampHoldMinutes(holdMinutes);
    const signalAmount = advancePaymentAmount.trim() ? Number(advancePaymentAmount) : null;
    if (paymentRequired && advancePaymentType === "signal" && (!signalAmount || signalAmount <= 0)) {
      setError("Informe um valor de sinal maior que zero.");
      return;
    }

    setSaving(true);
    try {
      const status = await updateMercadoPagoSettings({
        checkout_hold_minutes: normalizedHoldMinutes,
        payment_required_default: paymentRequired,
        advance_payment_type: paymentRequired ? advancePaymentType : null,
        advance_payment_amount: paymentRequired && advancePaymentType === "signal" ? signalAmount : null,
        default_provider: "mercado_pago",
      });
      syncForm(status);
      setSuccess("Configuracoes de pagamento salvas.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar pagamentos.");
    } finally {
      setSaving(false);
    }
  }

  if (!session || session.tenantId === "admin") return null;

  return (
    <main className={styles.page}>
      <div className={`app-container ${styles.shell}`}>
        <Link href="/" className={styles.backLink}>
          <ArrowLeft size={16} />
          Voltar
        </Link>

        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>Painel do estabelecimento</p>
            <h1 className={styles.title}>Pagamentos</h1>
            <p className={styles.subtitle}>
              Gerencie como os clientes pagam para confirmar agendamentos.
            </p>
          </div>
          <button className="btn btn-secondary" type="button" onClick={loadStatus} disabled={loading}>
            <RefreshCw size={16} />
            Atualizar
          </button>
        </header>

        {success ? <div className={styles.alertSuccess}>{success}</div> : null}
        {error ? <div className={styles.alertError}>{error}</div> : null}

        <section className={styles.statusPanel}>
          <div className={styles.statusHeader}>
            <div className={connected ? styles.statusIconConnected : styles.statusIconDisconnected}>
              {connected ? <CheckCircle2 size={24} /> : <Plug size={24} />}
            </div>
            <div>
              <h2 className={styles.panelTitle}>{statusLabel(account?.status)}</h2>
              <p className={styles.panelText}>
                {connected
                  ? "Recebimentos online prontos para os agendamentos."
                  : "Conecte sua conta Mercado Pago para receber pagamentos dos agendamentos."}
              </p>
            </div>
          </div>

          <div className={styles.statusRows}>
            <div className={styles.statusRow}>
              <Wallet size={18} />
              <span>Recebimento</span>
              <strong>{receivingStatus}</strong>
            </div>
            <div className={styles.statusRow}>
              <QrCode size={18} />
              <span>Pix</span>
              <strong>{connected && account?.pix_enabled !== false ? "habilitado" : "indisponivel"}</strong>
            </div>
            <div className={styles.statusRow}>
              <CreditCard size={18} />
              <span>Cartao</span>
              <strong>{connected && account?.card_enabled !== false ? "habilitado" : "indisponivel"}</strong>
            </div>
            <div className={styles.statusRow}>
              <Clock3 size={18} />
              <span>Ultima conexao</span>
              <strong>{formatDate(account?.connected_at)}</strong>
            </div>
          </div>

          <div className={styles.accountLine}>
            <ShieldCheck size={17} />
            <span>{accountHint}</span>
          </div>

          <div className={styles.actions}>
            {connected ? (
              <>
                <button className="btn btn-accent" type="button" onClick={handleConnect} disabled={Boolean(actionLoading)}>
                  <RefreshCw size={16} />
                  {actionLoading === "connect" ? "Abrindo..." : "Reconectar"}
                </button>
                <button className="btn btn-secondary" type="button" onClick={handleDisconnect} disabled={Boolean(actionLoading)}>
                  <Unplug size={16} />
                  {actionLoading === "disconnect" ? "Desconectando..." : "Desconectar"}
                </button>
              </>
            ) : (
              <button className="btn btn-accent" type="button" onClick={handleConnect} disabled={Boolean(actionLoading)}>
                <Plug size={16} />
                {actionLoading === "connect" ? "Abrindo..." : "Conectar Mercado Pago"}
              </button>
            )}
          </div>
        </section>

        <form className={styles.settingsPanel} onSubmit={handleSaveSettings}>
          <div className={styles.panelHeader}>
            <div>
              <h2 className={styles.panelTitle}>Configuracao do estabelecimento</h2>
              <p className={styles.panelText}>Defina quando o pagamento online sera usado nos agendamentos.</p>
            </div>
          </div>

          <div className={styles.formGrid}>
            <label className={styles.toggleRow}>
              <input
                type="checkbox"
                checked={paymentRequired}
                onChange={(event) => setPaymentRequired(event.target.checked)}
              />
              <span>
                <strong>Pagamento obrigatorio para confirmar agendamento</strong>
                <small>Quando ativo, o horario fica aguardando pagamento antes de confirmar.</small>
              </span>
            </label>

            <div className={styles.field}>
              <label htmlFor="hold-minutes">Tempo de bloqueio do horario</label>
              <div className={styles.numberInputWrap}>
                <input
                  id="hold-minutes"
                  className="input"
                  type="number"
                  min={5}
                  max={60}
                  value={holdMinutes}
                  onChange={(event) => setHoldMinutes(Number(event.target.value))}
                />
                <span>min</span>
              </div>
              <small>Entre 5 e 60 minutos.</small>
            </div>

            <div className={styles.field}>
              <span className={styles.labelText}>Forma de cobranca</span>
              <div className={styles.segmentedControl}>
                <button
                  type="button"
                  className={advancePaymentType === "full" ? styles.segmentActive : styles.segment}
                  onClick={() => setAdvancePaymentType("full")}
                  disabled={!paymentRequired}
                >
                  Valor total
                </button>
                <button
                  type="button"
                  className={advancePaymentType === "signal" ? styles.segmentActive : styles.segment}
                  onClick={() => setAdvancePaymentType("signal")}
                  disabled={!paymentRequired}
                >
                  Sinal
                </button>
              </div>
            </div>

            {advancePaymentType === "signal" ? (
              <div className={styles.field}>
                <label htmlFor="signal-amount">Valor do sinal</label>
                <input
                  id="signal-amount"
                  className="input"
                  type="number"
                  min={0.01}
                  step={0.01}
                  value={advancePaymentAmount}
                  onChange={(event) => setAdvancePaymentAmount(event.target.value)}
                  disabled={!paymentRequired}
                  placeholder="0,00"
                />
              </div>
            ) : null}

            <div className={styles.field}>
              <label htmlFor="default-provider">Recebimento padrao</label>
              <div className={styles.providerBox}>
                <Landmark size={18} />
                <span>{providerLabel(account?.default_provider)}</span>
              </div>
            </div>
          </div>

          <div className={styles.footer}>
            <button className="btn btn-accent" type="submit" disabled={saving || loading}>
              <Save size={16} />
              {saving ? "Salvando..." : "Salvar configuracoes"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}

export default function PainelPagamentosPage() {
  return (
    <Suspense fallback={<div className={styles.loadingState}>Carregando pagamentos...</div>}>
      <PaymentsPanelContent />
    </Suspense>
  );
}
