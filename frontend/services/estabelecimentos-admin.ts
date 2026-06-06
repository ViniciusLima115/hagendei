import { API_URL } from "./api";
import { getAuthSession } from "./auth";

export type PlanoEstabelecimento = "gratis" | "basico" | "premium";
export type StatusManualEstabelecimento = "ativo" | "inativo";
export type StatusAssinaturaEstabelecimento = "ativo" | "trial" | "bloqueado_atraso" | "inativo";

export type EstabelecimentoAdmin = {
  id: number;
  nome: string;
  login: string;
  senha: string;
  plano: PlanoEstabelecimento;
  statusManual: StatusManualEstabelecimento;
  vencimentoEm: string;
  trialAtivo: boolean;
  trialFimEm: string | null;
  ultimoAcessoEm: string | null;
  pagamentoRecusado: boolean;
  criadoEm: string;
  paymentAccountStatus?: "not_configured" | "connected" | "disconnected" | "expired" | "error";
  paymentAccountName?: string | null;
  paymentAccountId?: number | null;
  paymentProvider?: string | null;
  paymentConnectedAt?: string | null;
  paymentUpdatedAt?: string | null;
  paymentLastError?: string | null;
};

export type AdminPaymentAuditLogItem = {
  id: number;
  action: string;
  admin_sub?: string | null;
  status_before?: string | null;
  status_after?: string | null;
  error_message?: string | null;
  created_at: string;
};

export type AdminPaymentAccount = {
  id: number;
  establishment_id: number;
  provider: string;
  account_name: string | null;
  status: "connected" | "disconnected" | "expired" | "error";
  provider_account_id_masked?: string | null;
  provider_account_email_masked?: string | null;
  checkout_hold_minutes: number;
  connected_at?: string | null;
  disconnected_at?: string | null;
  expires_at?: string | null;
  created_at: string;
  updated_at: string;
  last_error?: string | null;
  last_payment_status?: string | null;
  last_payment_at?: string | null;
  last_test_payment_status?: string | null;
  last_test_payment_at?: string | null;
  approved_payments_count: number;
  failed_payments_count: number;
  audit_logs: AdminPaymentAuditLogItem[];
};

export type AdminPaymentEstablishment = {
  id: number;
  nome: string;
  slug: string | null;
  login: string | null;
  provider: string | null;
  payment_account_status: "not_configured" | "connected" | "disconnected" | "expired" | "error";
  payment_account_name: string | null;
  payment_account_id: number | null;
  connected_at?: string | null;
  updated_at?: string | null;
  last_error?: string | null;
};

export type AdminPaymentActionResponse = {
  status: string;
  detail: string;
  establishment_id: number;
  payment_account_id?: number | null;
  tested_at?: string | null;
};

// Backward compat aliases
export type BarbeariaAdmin = EstabelecimentoAdmin;
export type PlanoBarbearia = PlanoEstabelecimento;
export type StatusManualBarbearia = StatusManualEstabelecimento;
export type StatusAssinaturaBarbearia = StatusAssinaturaEstabelecimento;

type EstabelecimentoApi = {
  id: number;
  nome: string;
  login: string | null;
  senha: string | null;
  plano: PlanoEstabelecimento | null;
  status_manual: StatusManualEstabelecimento | null;
  vencimento_em: string | null;
  trial_ativo: boolean;
  trial_fim_em: string | null;
  ultimo_acesso_em: string | null;
  pagamento_recusado: boolean;
  criado_em: string;
};

function toISODateOnly(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function plusDays(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return toISODateOnly(date);
}

function toUi(item: EstabelecimentoApi): EstabelecimentoAdmin {
  return {
    id: item.id,
    nome: item.nome,
    login: item.login ?? "",
    senha: item.senha ?? "",
    plano: item.plano ?? "gratis",
    statusManual: item.status_manual ?? "ativo",
    vencimentoEm: item.vencimento_em ?? plusDays(30),
    trialAtivo: Boolean(item.trial_ativo),
    trialFimEm: item.trial_fim_em,
    ultimoAcessoEm: item.ultimo_acesso_em,
    pagamentoRecusado: Boolean(item.pagamento_recusado),
    criadoEm: item.criado_em,
  };
}

async function parseOrThrow(res: Response, fallback: string) {
  if (res.ok) return res.status === 204 ? null : res.json();
  const body = await res.json().catch(() => ({}));
  throw new Error(body?.detail || fallback);
}

function getAdminHeaders(contentTypeJson: boolean = false): HeadersInit {
  const token = getAuthSession()?.accessToken;
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (contentTypeJson) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

export async function listEstabelecimentosAdmin(): Promise<EstabelecimentoAdmin[]> {
  const res = await fetch(`${API_URL}/estabelecimentos/`, {
    cache: "no-store",
    headers: getAdminHeaders(),
  });
  const data = (await parseOrThrow(res, "Falha ao carregar estabelecimentos.")) as EstabelecimentoApi[];
  return data.map(toUi);
}

export async function listPaymentEstablishmentsAdmin(): Promise<AdminPaymentEstablishment[]> {
  const res = await fetch(`${API_URL}/admin/establishments`, {
    cache: "no-store",
    headers: getAdminHeaders(),
  });
  return parseOrThrow(res, "Falha ao carregar status de pagamentos dos estabelecimentos.");
}

// Backward compat alias
export const listBarbeariasAdmin = listEstabelecimentosAdmin;

export async function createEstabelecimentoAdmin(payload: {
  nome: string;
  login: string;
  senha: string;
  plano: PlanoEstabelecimento;
  vencimentoEm: string;
  trialAtivo: boolean;
  trialFimEm?: string | null;
  pagamentoRecusado?: boolean;
}): Promise<EstabelecimentoAdmin> {
  const res = await fetch(`${API_URL}/estabelecimentos/`, {
    method: "POST",
    headers: getAdminHeaders(true),
    body: JSON.stringify({
      nome: payload.nome.trim(),
      login: payload.login.trim(),
      senha: payload.senha,
      plano: payload.plano,
      status_manual: "ativo",
      vencimento_em: payload.vencimentoEm,
      trial_ativo: payload.trialAtivo,
      trial_fim_em: payload.trialAtivo ? payload.trialFimEm ?? null : null,
      ultimo_acesso_em: null,
      pagamento_recusado: Boolean(payload.pagamentoRecusado),
      endereco: "",
    }),
  });

  const data = (await parseOrThrow(res, "Falha ao cadastrar estabelecimento.")) as EstabelecimentoApi;
  return toUi(data);
}

// Backward compat alias
export const createBarbeariaAdmin = createEstabelecimentoAdmin;

export async function updateEstabelecimentoAdmin(
  id: number,
  payload: {
    nome: string;
    login: string;
    senha: string;
    plano: PlanoEstabelecimento;
    statusManual: StatusManualEstabelecimento;
    vencimentoEm: string;
    trialAtivo: boolean;
    trialFimEm: string | null;
    ultimoAcessoEm: string | null;
    pagamentoRecusado: boolean;
  }
): Promise<EstabelecimentoAdmin> {
  const res = await fetch(`${API_URL}/estabelecimentos/${id}`, {
    method: "PUT",
    headers: getAdminHeaders(true),
    body: JSON.stringify({
      nome: payload.nome.trim(),
      login: payload.login.trim(),
      senha: payload.senha,
      plano: payload.plano,
      status_manual: payload.statusManual,
      vencimento_em: payload.vencimentoEm,
      trial_ativo: payload.trialAtivo,
      trial_fim_em: payload.trialAtivo ? payload.trialFimEm : null,
      ultimo_acesso_em: payload.ultimoAcessoEm,
      pagamento_recusado: payload.pagamentoRecusado,
      endereco: "",
    }),
  });

  const data = (await parseOrThrow(res, "Falha ao atualizar estabelecimento.")) as EstabelecimentoApi;
  return toUi(data);
}

// Backward compat alias
export const updateBarbeariaAdmin = updateEstabelecimentoAdmin;

export async function deleteEstabelecimentoAdmin(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/estabelecimentos/${id}`, {
    method: "DELETE",
    headers: getAdminHeaders(),
  });
  await parseOrThrow(res, "Falha ao excluir estabelecimento.");
}

export async function getPaymentAccountAdmin(establishmentId: number): Promise<AdminPaymentAccount | null> {
  const res = await fetch(`${API_URL}/admin/establishments/${establishmentId}/payment-account`, {
    cache: "no-store",
    headers: getAdminHeaders(),
  });
  if (res.status === 404) return null;
  return parseOrThrow(res, "Falha ao carregar conta de pagamento.");
}

export async function deactivatePaymentAccountAdmin(establishmentId: number): Promise<AdminPaymentAccount> {
  const res = await fetch(`${API_URL}/admin/establishments/${establishmentId}/payment-account/deactivate`, {
    method: "POST",
    headers: getAdminHeaders(),
  });
  return parseOrThrow(res, "Falha ao desativar integracao de pagamento.");
}

export async function requestPaymentReconnectAdmin(establishmentId: number): Promise<AdminPaymentAccount> {
  const res = await fetch(`${API_URL}/admin/establishments/${establishmentId}/payment-account/request-reconnect`, {
    method: "POST",
    headers: getAdminHeaders(),
  });
  return parseOrThrow(res, "Falha ao solicitar reconexao.");
}

export async function testPaymentCheckoutAdmin(establishmentId: number): Promise<AdminPaymentActionResponse> {
  const res = await fetch(`${API_URL}/admin/establishments/${establishmentId}/payment-account/test-checkout`, {
    method: "POST",
    headers: getAdminHeaders(),
  });
  return parseOrThrow(res, "Falha ao testar checkout.");
}

// Backward compat alias
export const deleteBarbeariaAdmin = deleteEstabelecimentoAdmin;

export function getStatusAssinaturaEstabelecimento(item: EstabelecimentoAdmin): StatusAssinaturaEstabelecimento {
  if (item.statusManual === "inativo") return "inativo";

  const hoje = toISODateOnly(new Date());
  if (item.trialAtivo && item.trialFimEm && item.trialFimEm >= hoje) {
    return "trial";
  }

  if (item.vencimentoEm < hoje) {
    return "bloqueado_atraso";
  }

  return "ativo";
}

// Backward compat alias
export const getStatusAssinaturaBarbearia = getStatusAssinaturaEstabelecimento;
