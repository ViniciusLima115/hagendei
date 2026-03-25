"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Settings, User, Lock, Palette, Bell } from "lucide-react";
import { useAuthSession, AUTH_STORAGE_KEY } from "@/services/auth";
import { API_URL } from "@/services/api";

type Section = "perfil" | "senha" | "tema" | "notificacoes";

const SECTIONS: { id: Section; label: string; icon: React.ElementType }[] = [
  { id: "perfil", label: "Perfil", icon: User },
  { id: "senha", label: "Senha", icon: Lock },
  { id: "tema", label: "Tema", icon: Palette },
  { id: "notificacoes", label: "Notificações", icon: Bell },
];

async function patchConfiguracao(
  section: string,
  body: Record<string, unknown>,
  token: string,
): Promise<{ ok: boolean; detail?: string }> {
  try {
    const resp = await fetch(`${API_URL}/configuracoes/${section}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    return { ok: resp.ok, detail: data.detail };
  } catch {
    return { ok: false, detail: "Erro de conexão." };
  }
}

export default function ConfiguracoesPage() {
  const session = useAuthSession();
  const router = useRouter();
  const [activeSection, setActiveSection] = useState<Section>("perfil");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Perfil state
  const [nome, setNome] = useState(session?.tenantName ?? "");
  const [endereco, setEndereco] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [slug, setSlug] = useState("");

  // Senha state
  const [senhaAtual, setSenhaAtual] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmarSenha, setConfirmarSenha] = useState("");

  // Tema state
  const [accentColor, setAccentColor] = useState(session?.accentColor ?? "#d4930a");
  const [bgColor, setBgColor] = useState(session?.bgColor ?? "#ffffff");
  const [logoUrl, setLogoUrl] = useState(session?.logoUrl ?? "");

  // Notificações state
  const [notifAtivo, setNotifAtivo] = useState(true);
  const [notifHoras, setNotifHoras] = useState<number>(2);

  // Redirect admin
  useEffect(() => {
    if (session?.tenantId === "admin") {
      router.replace("/admin");
    }
  }, [session?.tenantId, router]);

  function clearMessages() {
    setSuccess(null);
    setError(null);
  }

  async function handleSalvarPerfil(e: React.FormEvent) {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    const result = await patchConfiguracao(
      "perfil",
      { nome: nome || undefined, endereco: endereco || undefined, whatsapp_number: whatsapp || undefined, slug: slug || undefined },
      session!.accessToken,
    );
    setLoading(false);
    if (result.ok) setSuccess("Perfil atualizado com sucesso!");
    else setError(result.detail ?? "Erro ao atualizar perfil.");
  }

  async function handleSalvarSenha(e: React.FormEvent) {
    e.preventDefault();
    clearMessages();
    if (novaSenha !== confirmarSenha) {
      setError("Nova senha e confirmação não coincidem.");
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
      session!.accessToken,
    );
    setLoading(false);
    if (result.ok) {
      setSuccess("Senha alterada com sucesso!");
      setSenhaAtual("");
      setNovaSenha("");
      setConfirmarSenha("");
    } else {
      setError(result.detail ?? "Erro ao alterar senha.");
    }
  }

  async function handleSalvarTema(e: React.FormEvent) {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    const result = await patchConfiguracao(
      "tema",
      {
        accent_color: accentColor,
        bg_color: bgColor,
        logo_url: logoUrl || null,
      },
      session!.accessToken,
    );
    setLoading(false);
    if (result.ok) {
      // Persist updated theme in localStorage
      if (typeof window !== "undefined") {
        const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
        if (raw) {
          try {
            const s = JSON.parse(raw);
            s.accentColor = accentColor;
            s.bgColor = bgColor;
            s.logoUrl = logoUrl || null;
            window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(s));
          } catch {}
        }
      }
      setSuccess("Tema atualizado com sucesso!");
    } else {
      setError(result.detail ?? "Erro ao atualizar tema.");
    }
  }

  async function handleSalvarNotificacoes(e: React.FormEvent) {
    e.preventDefault();
    clearMessages();
    setLoading(true);
    const result = await patchConfiguracao(
      "notificacoes",
      { notif_ativo: notifAtivo, notif_horas_antes: notifHoras },
      session!.accessToken,
    );
    setLoading(false);
    if (result.ok) setSuccess("Preferências salvas!");
    else setError(result.detail ?? "Erro ao salvar preferências.");
  }

  return (
    <main className="app-container" style={{ paddingTop: "2rem", paddingBottom: "3rem" }}>
      <div style={{ display: "flex", gap: "2rem", alignItems: "flex-start" }}>
        {/* Sidebar */}
        <aside
          style={{
            width: "200px",
            flexShrink: 0,
            background: "var(--surface)",
            borderRadius: "8px",
            padding: "1rem",
            border: "1px solid var(--line)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem", fontWeight: 700 }}>
            <Settings size={16} />
            <span>Configurações</span>
          </div>
          <nav style={{ display: "flex", flexDirection: "column", gap: "0.25rem" }}>
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => { setActiveSection(id); clearMessages(); }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.5rem 0.75rem",
                  borderRadius: "6px",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  background: activeSection === id ? "var(--accent)" : "transparent",
                  color: activeSection === id ? "#fff" : "var(--ink)",
                  fontWeight: activeSection === id ? 600 : 400,
                }}
              >
                <Icon size={14} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <div style={{ flex: 1, maxWidth: "600px" }}>
          {success && (
            <div style={{ background: "var(--success)", color: "#fff", padding: "0.75rem 1rem", borderRadius: "6px", marginBottom: "1rem" }}>
              {success}
            </div>
          )}
          {error && (
            <div style={{ background: "var(--danger)", color: "#fff", padding: "0.75rem 1rem", borderRadius: "6px", marginBottom: "1rem" }}>
              {error}
            </div>
          )}

          {activeSection === "perfil" && (
            <form onSubmit={handleSalvarPerfil}>
              <h2 style={{ marginBottom: "1.5rem" }}>Perfil do Estabelecimento</h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <label>
                  <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Nome</span>
                  <input className="mock-input" value={nome} onChange={e => setNome(e.target.value)} style={{ width: "100%" }} />
                </label>
                <label>
                  <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Endereço</span>
                  <input className="mock-input" value={endereco} onChange={e => setEndereco(e.target.value)} style={{ width: "100%" }} />
                </label>
                <label>
                  <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>WhatsApp</span>
                  <input className="mock-input" value={whatsapp} onChange={e => setWhatsapp(e.target.value)} style={{ width: "100%" }} />
                </label>
                <label>
                  <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Slug (URL pública)</span>
                  <input className="mock-input" value={slug} onChange={e => setSlug(e.target.value)} style={{ width: "100%" }} />
                </label>
                <button type="submit" className="mock-button" disabled={loading}>
                  {loading ? "Salvando..." : "Salvar perfil"}
                </button>
              </div>
            </form>
          )}

          {activeSection === "senha" && (
            <form onSubmit={handleSalvarSenha}>
              <h2 style={{ marginBottom: "1.5rem" }}>Trocar Senha</h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <label>
                  <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Senha atual</span>
                  <input type="password" className="mock-input" value={senhaAtual} onChange={e => setSenhaAtual(e.target.value)} style={{ width: "100%" }} />
                </label>
                <label>
                  <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Nova senha</span>
                  <input type="password" className="mock-input" value={novaSenha} onChange={e => setNovaSenha(e.target.value)} style={{ width: "100%" }} />
                </label>
                <label>
                  <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Confirmar nova senha</span>
                  <input type="password" className="mock-input" value={confirmarSenha} onChange={e => setConfirmarSenha(e.target.value)} style={{ width: "100%" }} />
                </label>
                <button type="submit" className="mock-button" disabled={loading}>
                  {loading ? "Salvando..." : "Alterar senha"}
                </button>
              </div>
            </form>
          )}

          {activeSection === "tema" && (
            <form onSubmit={handleSalvarTema}>
              <h2 style={{ marginBottom: "1.5rem" }}>Tema do Estabelecimento</h2>
              <p style={{ fontSize: "0.875rem", color: "var(--ink-2)", marginBottom: "1.5rem" }}>
                Personaliza a cor de destaque e o fundo tanto no painel quanto na página pública de agendamento.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                  <input
                    type="color"
                    value={accentColor}
                    onChange={e => {
                      setAccentColor(e.target.value);
                      document.documentElement.style.setProperty("--accent", e.target.value);
                    }}
                    style={{ width: "48px", height: "48px", border: "none", borderRadius: "4px", cursor: "pointer" }}
                  />
                  <div>
                    <div style={{ fontWeight: 600 }}>Cor de destaque</div>
                    <div style={{ fontSize: "0.875rem", color: "var(--ink-2)" }}>{accentColor}</div>
                  </div>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                  <input
                    type="color"
                    value={bgColor}
                    onChange={e => setBgColor(e.target.value)}
                    style={{ width: "48px", height: "48px", border: "none", borderRadius: "4px", cursor: "pointer" }}
                  />
                  <div>
                    <div style={{ fontWeight: 600 }}>Cor de fundo</div>
                    <div style={{ fontSize: "0.875rem", color: "var(--ink-2)" }}>{bgColor}</div>
                  </div>
                </label>
                <label>
                  <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>URL do logo (https://)</span>
                  <input
                    className="mock-input"
                    value={logoUrl ?? ""}
                    onChange={e => setLogoUrl(e.target.value)}
                    placeholder="https://example.com/logo.png"
                    style={{ width: "100%" }}
                  />
                  {logoUrl && (
                    <img
                      src={logoUrl}
                      alt="Preview do logo"
                      onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
                      style={{ marginTop: "0.5rem", height: "60px", objectFit: "contain" }}
                    />
                  )}
                </label>
                <button type="submit" className="mock-button" disabled={loading}>
                  {loading ? "Salvando..." : "Salvar tema"}
                </button>
              </div>
            </form>
          )}

          {activeSection === "notificacoes" && (
            <form onSubmit={handleSalvarNotificacoes}>
              <h2 style={{ marginBottom: "1.5rem" }}>Preferências de Notificação</h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <input
                    type="checkbox"
                    checked={notifAtivo}
                    onChange={e => setNotifAtivo(e.target.checked)}
                    style={{ width: "18px", height: "18px" }}
                  />
                  <span>Enviar lembretes de agendamento pelo WhatsApp</span>
                </label>
                <label>
                  <span style={{ display: "block", marginBottom: "0.25rem", fontSize: "0.875rem" }}>Avisar com quanto tempo de antecedência?</span>
                  <select
                    value={notifHoras}
                    onChange={e => setNotifHoras(Number(e.target.value))}
                    style={{ padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--line)", background: "var(--surface)", color: "var(--ink)" }}
                  >
                    <option value={1}>1 hora antes</option>
                    <option value={2}>2 horas antes</option>
                    <option value={4}>4 horas antes</option>
                    <option value={8}>8 horas antes</option>
                    <option value={24}>24 horas antes</option>
                  </select>
                </label>
                <p style={{ fontSize: "0.8rem", color: "var(--ink-2)" }}>
                  Nota: a integração dos lembretes com o scheduler está prevista para uma próxima versão.
                </p>
                <button type="submit" className="mock-button" disabled={loading}>
                  {loading ? "Salvando..." : "Salvar preferências"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
