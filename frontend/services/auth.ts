import { useSyncExternalStore } from "react";
import { API_URL } from "./api";

export type MeResponse = {
  id?: number;
  nome: string;
  plano: string;
  is_admin: boolean;
  tipo_servico?: string | null;
  accent_color?: string;
  bg_color?: string;
  logo_url?: string | null;
  notif_ativo?: boolean;
  notif_horas_antes?: number;
};

export async function fetchMe(): Promise<MeResponse | null> {
  try {
    const resp = await fetch(`${API_URL}/auth/me`, {
      credentials: "include",
      cache: "no-store",
    });
    if (!resp.ok) return null;
    return resp.json();
  } catch {
    return null;
  }
}

export const AUTH_STORAGE_KEY = "hagendei_auth_session";
const LEGACY_AUTH_STORAGE_KEY = "barbershop_auth_session";
const AUTH_CHANGE_EVENT = "hagendei_auth_changed";
const UI_SESSION_COOKIE_NAME = "hagendei_ui_session";

let cachedRawSession: string | null = null;
let cachedParsedSession: AuthSession | null = null;

export type AuthSession = {
  email: string;
  tenantId: string;
  tenantName: string;
  plan: "basico" | "premium";
  accentColor?: string;
  bgColor?: string;
  logoUrl?: string | null;
};

export function getAuthSession(): AuthSession | null {
  if (typeof window === "undefined") return null;

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (raw === cachedRawSession) return cachedParsedSession;

  cachedRawSession = raw;
  if (!raw) {
    cachedParsedSession = null;
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<AuthSession>;
    if (!parsed.email || !parsed.tenantId || !parsed.tenantName) {
      cachedParsedSession = null;
      return null;
    }
    cachedParsedSession = {
      email: parsed.email,
      tenantId: parsed.tenantId,
      tenantName: parsed.tenantName,
      plan: parsed.plan === "premium" ? "premium" : "basico",
      accentColor: parsed.accentColor,
      bgColor: parsed.bgColor,
      logoUrl: parsed.logoUrl ?? null,
    };
    return cachedParsedSession;
  } catch {
    cachedParsedSession = null;
    return null;
  }
}

export function isAuthenticated(): boolean {
  return Boolean(getAuthSession());
}

export function login(session: AuthSession): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(LEGACY_AUTH_STORAGE_KEY);
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${UI_SESSION_COOKIE_NAME}=1; Path=/; SameSite=Lax${secure}`;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function logout(): void {
  if (typeof window === "undefined") return;
  const session = getAuthSession();
  if (session?.tenantId) window.localStorage.removeItem(`notif_seen_${session.tenantId}`);

  void fetch(`${API_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
  }).catch(() => undefined);

  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  window.localStorage.removeItem(LEGACY_AUTH_STORAGE_KEY);
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${UI_SESSION_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
  cachedRawSession = null;
  cachedParsedSession = null;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

function subscribe(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const listener = () => onStoreChange();
  window.addEventListener("storage", listener);
  window.addEventListener(AUTH_CHANGE_EVENT, listener);
  return () => {
    window.removeEventListener("storage", listener);
    window.removeEventListener(AUTH_CHANGE_EVENT, listener);
  };
}

export function useAuthSession(): AuthSession | null {
  return useSyncExternalStore(subscribe, getAuthSession, () => null);
}
