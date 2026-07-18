"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Copy, LockKeyhole, ShieldCheck, TriangleAlert } from "lucide-react";
import { useAuthSession } from "@/services/auth";
import {
  AdminMfaSetup,
  AdminMfaStatus,
  confirmarMfaAdmin,
  desativarMfaAdmin,
  iniciarMfaAdmin,
  obterStatusMfaAdmin,
} from "@/services/api";
import styles from "./page.module.css";

export default function AdminSecurityPage() {
  const router = useRouter();
  const session = useAuthSession();
  const [status, setStatus] = useState<AdminMfaStatus | null>(null);
  const [setup, setSetup] = useState<AdminMfaSetup | null>(null);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);
  const [showDisable, setShowDisable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadStatus() {
    try {
      setStatus(await obterStatusMfaAdmin());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar a seguranca da conta.");
    }
  }

  useEffect(() => {
    if (!session) return;
    if (session.tenantId !== "admin") {
      router.replace("/admin");
      return;
    }
    void loadStatus();
  }, [session, router]);

  async function startSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      setSetup(await iniciarMfaAdmin(password));
      setPassword("");
      setCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao iniciar a configuracao.");
    } finally {
      setLoading(false);
    }
  }

  async function confirmSetup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await confirmarMfaAdmin(code);
      setRecoveryCodes(result.recovery_codes);
      setSetup(null);
      setCode("");
      setSuccess("Verificacao em duas etapas ativada.");
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Codigo invalido.");
    } finally {
      setLoading(false);
    }
  }

  async function disableMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await desativarMfaAdmin({ senha: password, code });
      setPassword("");
      setCode("");
      setShowDisable(false);
      setSuccess("Verificacao em duas etapas desativada. Todas as sessoes anteriores foram revogadas.");
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Nao foi possivel desativar a protecao.");
    } finally {
      setLoading(false);
    }
  }

  async function copy(value: string) {
    await navigator.clipboard.writeText(value);
    setSuccess("Copiado.");
  }

  if (!session || session.tenantId !== "admin") return null;

  return (
    <main className={styles.page}>
      <section className={styles.shell}>
        <Link href="/admin" className={styles.back}>Voltar ao painel</Link>
        <div className={styles.heading}>
          <div className={styles.icon}><ShieldCheck size={24} /></div>
          <div>
            <p className={styles.eyebrow}>Seguranca do superadmin</p>
            <h1>Verificacao em duas etapas</h1>
            <p>Proteja o acesso administrativo com o Google Authenticator.</p>
          </div>
        </div>

        {error && <div className={styles.noticeError}>{error}</div>}
        {success && <div className={styles.noticeSuccess}>{success}</div>}

        {!status ? <p className={styles.muted}>Carregando configuracao...</p> : null}

        {status && !status.enabled && !setup && !recoveryCodes && (
          <section className={styles.panel}>
            <div className={styles.panelIcon}><LockKeyhole size={20} /></div>
            <h2>Ative a protecao do administrador</h2>
            <p>Depois de ativar, senha sozinha nao sera suficiente para entrar no painel.</p>
            <form onSubmit={startSetup} className={styles.form}>
              <label htmlFor="setup-password">Confirme sua senha atual</label>
              <input id="setup-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
              <button type="submit" disabled={loading}>{loading ? "Preparando..." : "Configurar Google Authenticator"}</button>
            </form>
          </section>
        )}

        {setup && (
          <section className={styles.panel}>
            <div className={styles.steps}>
              <span>1</span><p>Abra o Google Authenticator e escaneie este QR Code.</p>
            </div>
            <Image className={styles.qr} src={setup.qr_code_data_url} alt="QR Code para Google Authenticator" width={224} height={224} unoptimized />
            <div className={styles.manualKey}>
              <span>Ou informe esta chave manualmente</span>
              <code>{setup.manual_key}</code>
              <button type="button" onClick={() => void copy(setup.manual_key)} aria-label="Copiar chave manual"><Copy size={16} /></button>
            </div>
            <form onSubmit={confirmSetup} className={styles.form}>
              <label htmlFor="setup-code">2. Digite o codigo de 6 numeros exibido no aplicativo</label>
              <input id="setup-code" inputMode="numeric" value={code} onChange={(event) => setCode(event.target.value)} autoComplete="one-time-code" placeholder="000000" required />
              <button type="submit" disabled={loading}>{loading ? "Confirmando..." : "Ativar verificacao"}</button>
              <button type="button" className={styles.secondary} onClick={() => setSetup(null)}>Cancelar</button>
            </form>
          </section>
        )}

        {recoveryCodes && (
          <section className={styles.panel}>
            <div className={styles.warningTitle}><TriangleAlert size={20} /><h2>Guarde os codigos de recuperacao</h2></div>
            <p>Eles aparecem somente agora. Use um deles caso perca acesso ao Google Authenticator.</p>
            <div className={styles.codes}>{recoveryCodes.map((item) => <code key={item}>{item}</code>)}</div>
            <button type="button" onClick={() => void copy(recoveryCodes.join("\n"))}><Copy size={16} /> Copiar codigos</button>
            <button type="button" className={styles.secondary} onClick={() => window.location.assign("/admin")}>Conclui e guardei os codigos</button>
          </section>
        )}

        {status?.enabled && !setup && !recoveryCodes && (
          <section className={styles.panel}>
            <div className={styles.activeTitle}><ShieldCheck size={20} /><h2>Protecao ativa</h2></div>
            <p>O superadmin precisa informar um codigo do autenticador a cada novo login.</p>
            <p className={styles.muted}>{status.recovery_codes_remaining} codigos de recuperacao restantes.</p>
            {!showDisable ? <button type="button" className={styles.danger} onClick={() => setShowDisable(true)}>Desativar verificacao em duas etapas</button> : (
              <form onSubmit={disableMfa} className={styles.form}>
                <label htmlFor="disable-password">Senha atual</label>
                <input id="disable-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
                <label htmlFor="disable-code">Codigo do autenticador ou recuperacao</label>
                <input id="disable-code" value={code} onChange={(event) => setCode(event.target.value)} autoComplete="one-time-code" required />
                <button type="submit" className={styles.danger} disabled={loading}>{loading ? "Desativando..." : "Confirmar desativacao"}</button>
                <button type="button" className={styles.secondary} onClick={() => setShowDisable(false)}>Cancelar</button>
              </form>
            )}
          </section>
        )}
      </section>
    </main>
  );
}
