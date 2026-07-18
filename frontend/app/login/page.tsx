"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Copy, Eye, Headset, Laptop, MessageCircle, ShieldCheck, User, X } from "lucide-react";
import { login, fetchMe } from "@/services/auth";
import { AdminMfaSetup, confirmarMfaAdmin, iniciarMfaAdmin, loginUsuario, verificarMfaAdmin } from "@/services/api";
import { PRODUCT_NAME } from "@/lib/brand";
import styles from "./page.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showSupportCard, setShowSupportCard] = useState(false);
  const [mfaChallenge, setMfaChallenge] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaSetup, setMfaSetup] = useState<AdminMfaSetup | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null);

  function concluirLoginAdmin(usuario: string) {
    login({
      email: usuario,
      tenantId: "admin",
      tenantName: "Administrador",
      plan: "premium",
    });
    router.replace("/");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const usuario = email.trim();
    const senha = password;

    if (!usuario || !senha) {
      setError("Preencha todos os campos para entrar.");
      return;
    }

    setLoading(true);

    try {
      const resposta = await loginUsuario({
        usuario,
        senha,
      });

      if (resposta.mfa_required && resposta.mfa_challenge) {
        setMfaChallenge(resposta.mfa_challenge);
        setMfaCode("");
        setPassword("");
        return;
      }

      if (resposta.mfa_setup_required && resposta.is_admin) {
        setMfaSetup(await iniciarMfaAdmin(senha));
        setMfaCode("");
        setPassword("");
        return;
      }

      if (resposta.is_admin) {
        concluirLoginAdmin(usuario);
        return;
      }

      if (!resposta.tenant_id || !resposta.tenant_name) {
        setError("Nao foi possivel identificar o estabelecimento do usuario.");
        return;
      }

      const me = await fetchMe();
      login({
        email: usuario,
        tenantId: String(resposta.tenant_id),
        tenantName: resposta.tenant_name,
        plan: resposta.plano === "premium" ? "premium" : "basico",
        accentColor: me?.accent_color,
        bgColor: me?.bg_color,
        logoUrl: me?.logo_url,
      });

      router.replace("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nao foi possivel iniciar sessao.");
    } finally {
      setLoading(false);
    }
  }

  async function handleMfaSetupSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const code = mfaCode.trim();
    if (!mfaSetup || !code) {
      setError("Informe o codigo de 6 digitos exibido no Google Authenticator.");
      return;
    }
    setLoading(true);
    try {
      const result = await confirmarMfaAdmin(code);
      login({
        email: email.trim(),
        tenantId: "admin",
        tenantName: "Administrador",
        plan: "premium",
      });
      setRecoveryCodes(result.recovery_codes);
      setMfaSetup(null);
      setMfaCode("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nao foi possivel ativar o autenticador.");
    } finally {
      setLoading(false);
    }
  }

  async function copyRecoveryCodes() {
    if (!recoveryCodes) return;
    await navigator.clipboard.writeText(recoveryCodes.join("\n"));
  }

  async function handleMfaSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const code = mfaCode.trim().toUpperCase();
    if (!mfaChallenge || !code) {
      setError("Informe o codigo do aplicativo autenticador.");
      return;
    }
    setLoading(true);
    try {
      const resposta = await verificarMfaAdmin({ challenge: mfaChallenge, code });
      if (!resposta.is_admin) throw new Error("Nao foi possivel concluir a verificacao.");
      concluirLoginAdmin(email.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nao foi possivel validar o codigo.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      {/* PAINEL ESQUERDO — branding */}
      <div className={styles.left}>
        <div className={styles.leftBrand}>
          <div className={styles.leftIcon}>
            {/* Laptop já é o ícone usado no login atual — mantido por consistência */}
            <Laptop size={18} color="white" />
          </div>
          <div>
            <div className={styles.leftEyebrow}>Sistema de gestão</div>
            <div className={styles.leftBrandName}>{PRODUCT_NAME}</div>
          </div>
        </div>

        <div className={styles.leftCopy}>
          <h1 className={styles.leftTitle}>Seu negócio,<br />bem gerido.</h1>
          <div className={styles.leftDivider} />
          <div className={styles.socialProof}>
            <div className={styles.avatars}>
              <div className={styles.avatar}>CA</div>
              <div className={styles.avatar}>MB</div>
              <div className={styles.avatar}>+</div>
            </div>
            <div className={styles.socialText}>
              <strong>+50 estabelecimentos</strong><br />já usam o sistema
            </div>
          </div>
        </div>
      </div>

      {/* PAINEL DIREITO — formulário */}
      <div className={styles.right}>
        <p className={styles.formEyebrow}>Área restrita</p>
        <h2 className={styles.formTitle}>Bem-vindo<br />de volta.</h2>
        <p className={styles.formSub}>Acesse o painel do seu estabelecimento.</p>

        <form onSubmit={mfaSetup ? handleMfaSetupSubmit : mfaChallenge ? handleMfaSubmit : handleSubmit} className={styles.form}>
          <div className={styles.field} style={{ display: mfaChallenge || mfaSetup || recoveryCodes ? "none" : undefined }}>
            <label htmlFor="email" className={styles.label}>Usuário</label>
            <div className={styles.inputWrap}>
              <input
                id="email"
                type="text"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={styles.input}
                placeholder="Digite seu usuário"
                autoComplete="username"
              />
              <User size={16} className={styles.inputIcon} />
            </div>
          </div>

          <div className={styles.field} style={{ display: mfaChallenge || mfaSetup || recoveryCodes ? "none" : undefined }}>
            <label htmlFor="password" className={styles.label}>Senha</label>
            <div className={styles.inputWrap}>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={styles.input}
                placeholder="Digite sua senha"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className={styles.ghostButton}
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
              >
                <Eye size={16} />
              </button>
            </div>
          </div>

          {mfaChallenge && (
            <>
              <div className={styles.mfaIntro}>
                <ShieldCheck size={18} />
                <span>Verificacao em duas etapas</span>
              </div>
              <div className={styles.field}>
                <label htmlFor="mfa-code" className={styles.label}>Codigo de seguranca</label>
                <input
                  id="mfa-code"
                  type="text"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  className={styles.input}
                  placeholder="000000 ou ABCD-EFGH"
                  autoComplete="one-time-code"
                  autoFocus
                />
              </div>
            </>
          )}

          {mfaSetup && (
            <div className={styles.setupBox}>
              <div className={styles.mfaIntro}>
                <ShieldCheck size={18} />
                <span>Configure o Google Authenticator</span>
              </div>
              <p className={styles.setupText}>Escaneie o QR Code e informe o codigo atual de 6 digitos.</p>
              <Image className={styles.setupQr} src={mfaSetup.qr_code_data_url} alt="QR Code do Google Authenticator" width={184} height={184} unoptimized />
              <div className={styles.setupKey}>
                <span>Chave manual</span>
                <code>{mfaSetup.manual_key}</code>
              </div>
              <div className={styles.field}>
                <label htmlFor="mfa-setup-code" className={styles.label}>Codigo do aplicativo</label>
                <input id="mfa-setup-code" type="text" inputMode="numeric" value={mfaCode} onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))} className={styles.input} placeholder="000000" autoComplete="one-time-code" autoFocus />
              </div>
            </div>
          )}

          {recoveryCodes && (
            <div className={styles.setupBox}>
              <div className={styles.mfaIntro}>
                <ShieldCheck size={18} />
                <span>Autenticador ativado</span>
              </div>
              <p className={styles.setupText}>Guarde estes codigos. Cada um pode ser usado uma unica vez.</p>
              <div className={styles.recoveryGrid}>{recoveryCodes.map((item) => <code key={item}>{item}</code>)}</div>
              <button type="button" className={styles.copyButton} onClick={() => void copyRecoveryCodes()}><Copy size={15} /> Copiar codigos</button>
            </div>
          )}

          {error && <div className={styles.error}>{error}</div>}

          {!recoveryCodes && <button
            type="submit"
            className={styles.submit}
            disabled={loading}
          >
            {loading ? (mfaSetup ? "Ativando..." : mfaChallenge ? "Verificando..." : "Entrando...") : (mfaSetup ? "Ativar e entrar" : mfaChallenge ? "Verificar e entrar" : "Entrar")}
          </button>}
          {recoveryCodes && <button type="button" className={styles.submit} onClick={() => window.location.assign("/admin")}>Continuar para o painel</button>}
        </form>

        {!mfaChallenge && !mfaSetup && !recoveryCodes && <button
          type="button"
          onClick={() => setShowSupportCard(true)}
          className={styles.supportLink}
        >
          Esqueceu a senha? Fale com o suporte
        </button>}
        {mfaChallenge && <button type="button" className={styles.supportLink} onClick={() => { setMfaChallenge(null); setMfaCode(""); setError(null); }}>
          Voltar ao login
        </button>}
      </div>

      {/* SUPPORT CARD OVERLAY */}
      {showSupportCard && (
        <div className={styles.overlay}>
          <div className={styles.supportCard}>
            <div className={styles.supportHeader}>
              <div className={styles.supportIntro}>
                <span className={styles.supportIcon}>
                  <Headset size={18} />
                </span>
                <div>
                  <p className={styles.supportTitle}>Contate o suporte</p>
                  <p className={styles.supportSub}>Recuperação de acesso</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowSupportCard(false)}
                className="icon-button"
                aria-label="Fechar card de suporte"
              >
                <X size={16} />
              </button>
            </div>
            <p className={styles.supportText}>
              Para recuperar sua senha, fale com nosso atendimento.
            </p>
            <div className={styles.supportActions}>
              <a
                href="https://wa.me/5582999627481"
                target="_blank"
                rel="noreferrer"
                className={styles.whatsButton}
              >
                <MessageCircle size={16} />
                Falar no WhatsApp
              </a>
              <button
                type="button"
                onClick={() => setShowSupportCard(false)}
                className={styles.closeButton}
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
