"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Settings, User, Lock, Palette, Bell, ArrowLeft } from "lucide-react";

import { fetchMe, updateAuthSession, useAuthSession } from "@/services/auth";
import { API_URL } from "@/services/api";
import {
  applyTenantTheme,
  DEFAULT_ACCENT_COLOR,
  DEFAULT_BACKGROUND_COLOR,
} from "@/lib/theme";
import styles from "./page.module.css";

type Section = "perfil" | "senha" | "tema" | "notificacoes";

const SECTIONS: { id: Section; label: string; icon: React.ElementType }[] = [
  { id: "perfil", label: "Perfil", icon: User },
  { id: "senha", label: "Senha", icon: Lock },
  { id: "tema", label: "Tema", icon: Palette },
  { id: "notificacoes", label: "Notificacoes", icon: Bell },
];

type Preset = {
  label: string;
  accent: string;
  bg: string;
};

const PRESETS: Preset[] = [
  { label: "Petroleo", accent: "#1e3a5f", bg: "#ffffff" },
  { label: "Teal", accent: "#0d9488", bg: "#ffffff" },
  { label: "Rosa", accent: "#db2777", bg: "#ffffff" },
  { label: "Ambar", accent: "#d99b3f", bg: "#ffffff" },
  { label: "Ardosia", accent: "#475569", bg: "#f8fafc" },
  { label: "Coral", accent: "#e2522b", bg: "#fffaf8" },
  { label: "Noturno", accent: "#e5a820", bg: "#0f0f0e" },
];

function formatApiDetail(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return undefined;

  const messages = detail
    .map((item) => {
      if (!item || typeof item !== "object" || !("msg" in item)) return "";
      const record = item as { msg?: unknown; loc?: unknown };
      const location = Array.isArray(record.loc)
        ? record.loc.filter((part) => part !== "body").join(".")
        : "";
      const message = typeof record.msg === "string" ? record.msg : "";
      return location && message ? `${location}: ${message}` : message;
    })
    .filter(Boolean);

  return messages.length ? messages.join(" ") : undefined;
}

async function patchConfiguracao(
  section: string,
  body: Record<string, unknown>,
): Promise<{ ok: boolean; detail?: string }> {
  try {
    const resp = await fetch(`${API_URL}/configuracoes/${section}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(body),
    });
    const data = await resp.json().catch(() => ({}));
    return { ok: resp.ok, detail: formatApiDetail(data.detail) };
  } catch {
    return { ok: false, detail: "Erro de conexao." };
  }
}

function ConfiguracoesContent() {
  const session = useAuthSession();
  const router = useRouter();
  const searchParams = useSearchParams();

  const requestedSection = searchParams.get("aba");
  const activeSection: Section =
    requestedSection === "senha" ||
    requestedSection === "tema" ||
    requestedSection === "notificacoes"
      ? requestedSection
      : "perfil";
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [nome, setNome] = useState(session?.tenantName ?? "");
  const [endereco, setEndereco] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [slug, setSlug] = useState("");

  const [senhaAtual, setSenhaAtual] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmarSenha, setConfirmarSenha] = useState("");

  const [accentColor, setAccentColor] = useState(session?.accentColor ?? DEFAULT_ACCENT_COLOR);
  const [bgColor, setBgColor] = useState(session?.bgColor ?? DEFAULT_BACKGROUND_COLOR);
  const [logoUrl, setLogoUrl] = useState(session?.logoUrl ?? "");
  const [activePreset, setActivePreset] = useState<string | null>(null);

  const [notifAtivo, setNotifAtivo] = useState(true);
  const [notifHoras, setNotifHoras] = useState<number>(2);

  useEffect(() => {
    if (session?.tenantId === "admin") router.replace("/admin");
  }, [session?.tenantId, router]);

  useEffect(() => {
    const tenantId = session?.tenantId;
    if (!tenantId || tenantId === "admin") {
      return;
    }

    let active = true;
    const loadingFrame = window.requestAnimationFrame(() => {
      setInitialLoading(true);
    });

    void fetchMe()
      .then((profile) => {
        if (!active) return;
        if (!profile) {
          setError("Nao foi possivel carregar as configuracoes atuais.");
          return;
        }

        const nextAccent = profile.accent_color ?? DEFAULT_ACCENT_COLOR;
        const nextBackground = profile.bg_color ?? DEFAULT_BACKGROUND_COLOR;
        setNome(profile.nome ?? "");
        setEndereco(profile.endereco ?? "");
        setWhatsapp(profile.whatsapp_number ?? "");
        setSlug(profile.slug ?? "");
        setAccentColor(nextAccent);
        setBgColor(nextBackground);
        setLogoUrl(profile.logo_url ?? "");
        setNotifAtivo(profile.notif_ativo ?? true);
        setNotifHoras(profile.notif_horas_antes ?? 2);
        setActivePreset(
          PRESETS.find(
            (preset) => preset.accent === nextAccent && preset.bg === nextBackground,
          )?.label ?? null,
        );
        updateAuthSession({
          tenantName: profile.nome,
          plan:
            profile.plano === "premium"
              ? "premium"
              : profile.plano === "basico"
                ? "basico"
                : "gratis",
          accentColor: nextAccent,
          bgColor: nextBackground,
          logoUrl: profile.logo_url ?? null,
        });
      })
      .finally(() => {
        window.cancelAnimationFrame(loadingFrame);
        if (active) setInitialLoading(false);
      });

    return () => {
      active = false;
      window.cancelAnimationFrame(loadingFrame);
    };
  }, [session?.tenantId]);

  useEffect(() => {
    if (!session) return;
    const frame = window.requestAnimationFrame(() => {
      const nextAccent = session.accentColor ?? DEFAULT_ACCENT_COLOR;
      const nextBackground = session.bgColor ?? DEFAULT_BACKGROUND_COLOR;
      setAccentColor(nextAccent);
      setBgColor(nextBackground);
      setLogoUrl(session.logoUrl ?? "");
      setActivePreset(
        PRESETS.find(
          (preset) => preset.accent === nextAccent && preset.bg === nextBackground,
        )?.label ?? null,
      );
    });

    return () => window.cancelAnimationFrame(frame);
  }, [session]);

  useEffect(() => {
    return () => {
      applyTenantTheme(
        document.documentElement,
        session?.accentColor ?? DEFAULT_ACCENT_COLOR,
        session?.bgColor ?? DEFAULT_BACKGROUND_COLOR,
      );
    };
  }, [session?.accentColor, session?.bgColor]);

  function clearMessages() {
    setSuccess(null);
    setError(null);
  }

  function previewTheme(accent: string, background: string) {
    applyTenantTheme(document.documentElement, accent, background);
  }

  function applyPreset(preset: Preset) {
    setAccentColor(preset.accent);
    setBgColor(preset.bg);
    setActivePreset(preset.label);
    previewTheme(preset.accent, preset.bg);
  }

  async function handleSalvarPerfil(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    clearMessages();
    setLoading(true);
    const result = await patchConfiguracao(
      "perfil",
      {
        nome: nome || undefined,
        endereco: endereco || undefined,
        whatsapp_number: whatsapp || undefined,
        slug: slug || undefined,
      },
    );
    setLoading(false);
    if (result.ok) {
      if (nome.trim()) updateAuthSession({ tenantName: nome.trim() });
      setSuccess("Perfil atualizado com sucesso.");
    } else {
      setError(result.detail ?? "Erro ao atualizar perfil.");
    }
  }

  async function handleSalvarSenha(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    clearMessages();
    if (novaSenha !== confirmarSenha) {
      setError("Nova senha e confirmacao nao coincidem.");
      return;
    }
    if (novaSenha.length < 8) {
      setError("A nova senha deve ter pelo menos 8 caracteres.");
      return;
    }

    setLoading(true);
    const result = await patchConfiguracao(
      "senha",
      { senha_atual: senhaAtual, nova_senha: novaSenha },
    );
    setLoading(false);

    if (result.ok) {
      setSuccess("Senha alterada com sucesso.");
      setSenhaAtual("");
      setNovaSenha("");
      setConfirmarSenha("");
    } else {
      setError(result.detail ?? "Erro ao alterar senha.");
    }
  }

  async function handleSalvarTema(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    clearMessages();

    setLoading(true);
    const result = await patchConfiguracao(
      "tema",
      { accent_color: accentColor, bg_color: bgColor, logo_url: logoUrl || null },
    );
    setLoading(false);

    if (result.ok) {
      updateAuthSession({
        accentColor,
        bgColor,
        logoUrl: logoUrl || null,
      });
      previewTheme(accentColor, bgColor);
      setSuccess("Tema salvo e aplicado ao painel e a pagina publica.");
    } else {
      previewTheme(
        session.accentColor ?? DEFAULT_ACCENT_COLOR,
        session.bgColor ?? DEFAULT_BACKGROUND_COLOR,
      );
      setError(result.detail ?? "Erro ao salvar tema.");
    }
  }

  async function handleSalvarNotificacoes(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    clearMessages();

    setLoading(true);
    const result = await patchConfiguracao(
      "notificacoes",
      { notif_ativo: notifAtivo, notif_horas_antes: notifHoras },
    );
    setLoading(false);
    if (result.ok) setSuccess("Preferencias salvas.");
    else setError(result.detail ?? "Erro ao salvar preferencias.");
  }

  return (
    <div className={styles.page}>
      <div className={styles.shell}>
        <aside className={styles.sidebar}>
          <button type="button" onClick={() => router.back()} className={styles.backButton}>
            <ArrowLeft size={14} />
            Voltar
          </button>
          <div className={styles.sidebarHeader}>
            <Settings size={15} />
            Configuracoes
          </div>
          <nav className={styles.navList}>
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={`${styles.navItem} ${activeSection === id ? styles.navItemActive : ""}`}
                onClick={() => {
                  router.replace(`/configuracoes?aba=${id}`, { scroll: false });
                  clearMessages();
                }}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </nav>
        </aside>

        <div className={styles.content}>
          {success && <div className={styles.alertSuccess}>{success}</div>}
          {error && <div className={styles.alertError}>{error}</div>}

          {activeSection === "perfil" && (
            <form onSubmit={handleSalvarPerfil} className={styles.card}>
              <div className={styles.cardHeader}>
                <p className={styles.eyebrow}>Conta</p>
                <h2 className={styles.cardTitle}>Perfil do estabelecimento</h2>
                <p className={styles.cardDesc}>Informacoes publicas exibidas no agendamento.</p>
              </div>

              <div className={styles.cardBody}>
                <div className={styles.fieldGroup}>
                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="nome">Nome do estabelecimento</label>
                    <input id="nome" className="input" value={nome} onChange={(e) => setNome(e.target.value)} />
                  </div>
                  <hr className={styles.divider} />
                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="endereco">Endereco</label>
                    <input id="endereco" className="input" value={endereco} onChange={(e) => setEndereco(e.target.value)} />
                  </div>
                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="whatsapp">WhatsApp</label>
                    <input id="whatsapp" className="input" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} />
                  </div>
                  <hr className={styles.divider} />
                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="slug">Slug (URL publica)</label>
                    <input id="slug" className="input" value={slug} onChange={(e) => setSlug(e.target.value)} />
                    <span className={styles.fieldHint}>Seu link publico usa este identificador.</span>
                  </div>
                </div>
              </div>

              <div className={styles.cardFooter}>
                <button type="submit" className="btn btn-accent" disabled={loading || initialLoading}>
                  {loading || initialLoading ? "Salvando..." : "Salvar perfil"}
                </button>
              </div>
            </form>
          )}

          {activeSection === "senha" && (
            <form onSubmit={handleSalvarSenha} className={styles.card}>
              <div className={styles.cardHeader}>
                <p className={styles.eyebrow}>Seguranca</p>
                <h2 className={styles.cardTitle}>Trocar senha</h2>
                <p className={styles.cardDesc}>Use uma senha forte com pelo menos 8 caracteres.</p>
              </div>

              <div className={styles.cardBody}>
                <div className={styles.fieldGroup}>
                  <div className={styles.field}>
                    <label className={styles.fieldLabel}>Senha atual</label>
                    <input type="password" className="input" value={senhaAtual} onChange={(e) => setSenhaAtual(e.target.value)} />
                  </div>
                  <hr className={styles.divider} />
                  <div className={styles.fieldRow}>
                    <div className={styles.field}>
                      <label className={styles.fieldLabel}>Nova senha</label>
                      <input type="password" className="input" value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)} />
                    </div>
                    <div className={styles.field}>
                      <label className={styles.fieldLabel}>Confirmar nova senha</label>
                      <input type="password" className="input" value={confirmarSenha} onChange={(e) => setConfirmarSenha(e.target.value)} />
                    </div>
                  </div>
                </div>
              </div>

              <div className={styles.cardFooter}>
                <button type="submit" className="btn btn-accent" disabled={loading || initialLoading}>
                  {loading || initialLoading ? "Salvando..." : "Alterar senha"}
                </button>
              </div>
            </form>
          )}

          {activeSection === "tema" && (
            <form onSubmit={handleSalvarTema} className={styles.card}>
              <div className={styles.cardHeader}>
                <p className={styles.eyebrow}>Aparencia</p>
                <h2 className={styles.cardTitle}>Tema e cores</h2>
                <p className={styles.cardDesc}>Personalize cores do painel e da pagina publica.</p>
              </div>

              <div className={styles.cardBody}>
                <div className={styles.fieldGroup}>
                  <div className={styles.field}>
                    <span className={styles.fieldLabel}>Paletas prontas</span>
                    <div className={styles.presetGrid}>
                      {PRESETS.map((preset) => (
                        <button
                          key={preset.label}
                          type="button"
                          className={`${styles.presetChip} ${activePreset === preset.label ? styles.presetChipActive : ""}`}
                          onClick={() => applyPreset(preset)}
                        >
                          <span className={styles.presetDot} style={{ background: preset.accent }} />
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <hr className={styles.divider} />

                  <div className={styles.colorPickerRow}>
                    <div className={styles.colorPickerField}>
                      <span className={styles.fieldLabel}>Cor de destaque</span>
                      <div className={styles.colorPickerTrigger}>
                        <span className={styles.colorSwatch} style={{ background: accentColor }} />
                        <span className={styles.colorHex}>{accentColor}</span>
                        <input
                          type="color"
                          className={styles.colorPickerInput}
                          value={accentColor}
                          onChange={(e) => {
                            const nextAccent = e.target.value;
                            setAccentColor(nextAccent);
                            setActivePreset(null);
                            previewTheme(nextAccent, bgColor);
                          }}
                        />
                      </div>
                    </div>

                    <div className={styles.colorPickerField}>
                      <span className={styles.fieldLabel}>Cor de fundo</span>
                      <div className={styles.colorPickerTrigger}>
                        <span className={styles.colorSwatch} style={{ background: bgColor }} />
                        <span className={styles.colorHex}>{bgColor}</span>
                        <input
                          type="color"
                          className={styles.colorPickerInput}
                          value={bgColor}
                          onChange={(e) => {
                            const nextBackground = e.target.value;
                            setBgColor(nextBackground);
                            setActivePreset(null);
                            previewTheme(accentColor, nextBackground);
                          }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className={styles.field}>
                    <label className={styles.fieldLabel} htmlFor="logo-url">URL do logotipo</label>
                    <input id="logo-url" className="input" value={logoUrl ?? ""} onChange={(e) => setLogoUrl(e.target.value)} />
                    {/* URLs de tenant nao passam pelo otimizador do servidor, evitando fetch interno. */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    {logoUrl && <img src={logoUrl} alt="Preview do logo" className={styles.logoPreview} />}
                  </div>
                </div>
              </div>

              <div className={styles.cardFooter}>
                <button type="submit" className="btn btn-accent" disabled={loading || initialLoading}>
                  {loading || initialLoading ? "Salvando..." : "Salvar tema"}
                </button>
              </div>
            </form>
          )}

          {activeSection === "notificacoes" && (
            <form onSubmit={handleSalvarNotificacoes} className={styles.card}>
              <div className={styles.cardHeader}>
                <p className={styles.eyebrow}>Automacoes</p>
                <h2 className={styles.cardTitle}>Notificacoes</h2>
                <p className={styles.cardDesc}>Configure lembretes automaticos enviados aos clientes.</p>
              </div>

              <div className={styles.cardBody}>
                <div className={styles.fieldGroup}>
                  <label className={styles.checkboxRow}>
                    <input type="checkbox" checked={notifAtivo} onChange={(e) => setNotifAtivo(e.target.checked)} />
                    <div>
                      <div className={styles.checkboxLabel}>Enviar lembretes de agendamento</div>
                      <div className={styles.checkboxHint}>Mensagens automaticas por WhatsApp antes do horario.</div>
                    </div>
                  </label>

                  <hr className={styles.divider} />

                  <div className={styles.field}>
                    <label className={styles.fieldLabel}>Antecedencia do lembrete</label>
                    <select className="input" value={notifHoras} onChange={(e) => setNotifHoras(Number(e.target.value))} disabled={!notifAtivo}>
                      <option value={1}>1 hora antes</option>
                      <option value={2}>2 horas antes</option>
                      <option value={4}>4 horas antes</option>
                      <option value={8}>8 horas antes</option>
                      <option value={24}>24 horas antes</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className={styles.cardFooter}>
                <button type="submit" className="btn btn-accent" disabled={loading || initialLoading}>
                  {loading || initialLoading ? "Salvando..." : "Salvar preferencias"}
                </button>
              </div>
            </form>
          )}

        </div>
      </div>
    </div>
  );
}

export default function ConfiguracoesPage() {
  return (
    <Suspense fallback={<div>Carregando...</div>}>
      <ConfiguracoesContent />
    </Suspense>
  );
}
