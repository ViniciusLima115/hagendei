import { API_URL } from "./api";

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
<<<<<<< HEAD
  paymentAccountStatus?: "not_configured" | "active" | "inactive" | "error" | "revoked" | "pending" | "pending_validation" | "disconnected";
  paymentAccountName?: string | null;
  paymentAccountId?: number | null;
  paymentEnvironment?: "sandbox" | "production" | null;
  paymentValidationStatus?: "valid" | "invalid" | "not_validated" | "error" | null;
=======
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
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
};

export type AdminPaymentAccount = {
  id: number;
  establishment_id: number;
  provider: string;
  environment: "sandbox" | "production";
  account_name: string | null;
<<<<<<< HEAD
  status: "active" | "inactive" | "error" | "revoked" | "pending" | "pending_validation" | "disconnected";
  client_id_masked: string | null;
  client_secret_masked: string | null;
  access_token_masked: string | null;
  webhook_secret_masked: string | null;
  public_key_masked: string | null;
  internal_notes: string | null;
  checkout_hold_minutes: number;
  validation_status: "valid" | "invalid" | "not_validated" | "error";
  validation_error: string | null;
  last_validated_at: string | null;
  connected_at: string | null;
  disconnected_at: string | null;
=======
  status: "connected" | "disconnected" | "expired" | "error";
  provider_account_id_masked?: string | null;
  provider_account_email_masked?: string | null;
  checkout_hold_minutes: number;
  connected_at?: string | null;
  disconnected_at?: string | null;
  expires_at?: string | null;
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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

export type AdminPaymentIntegration = {
  provider: string;
  environment: "sandbox" | "production";
  status: "active" | "inactive" | "error" | "pending_validation" | "disconnected";
  validation_status: "valid" | "invalid" | "not_validated" | "error";
  last_validated_at: string | null;
  connected_at: string | null;
  updated_at: string;
  updated_by: string | null;
  public_key_masked: string | null;
  access_token_masked: string | null;
  webhook_secret_masked: string | null;
  has_client_id: boolean;
  has_client_secret: boolean;
};

export type AdminPaymentIntegrationValidation = {
  valid: boolean;
  validation_status: "valid" | "invalid" | "error";
  message: string;
  last_validated_at: string | null;
};

export type AdminPaymentIntegrationTestCheckout = {
  provider: string;
  environment: "sandbox" | "production";
  preference_id: string;
  checkout_url: string;
  status: "created";
};

export type AdminPaymentEstablishment = {
  id: number;
  nome: string;
  slug: string | null;
  login: string | null;
<<<<<<< HEAD
  payment_account_status: "not_configured" | "active" | "inactive" | "error" | "revoked" | "pending" | "pending_validation" | "disconnected";
  payment_account_name: string | null;
  payment_account_id: number | null;
  payment_environment: "sandbox" | "production" | null;
  payment_validation_status: "valid" | "invalid" | "not_validated" | "error" | null;
=======
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
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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

function formatApiDetail(detail: unknown): string | null {
  if (!detail) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          const record = item as { msg?: unknown; loc?: unknown };
          const location = Array.isArray(record.loc) ? record.loc.filter((part) => part !== "body").join(".") : "";
          const message = typeof record.msg === "string" ? record.msg : "";
          return location && message ? `${location}: ${message}` : message;
        }
        return "";
      })
      .filter(Boolean);
    return messages.length ? messages.join(" ") : null;
  }
  return null;
}

async function parseOrThrow(res: Response, fallback: string) {
  if (res.ok) return res.status === 204 ? null : res.json();
  const body = await res.json().catch(() => ({}));
  throw new Error(formatApiDetail(body?.detail) || fallback);
}

function getAdminHeaders(contentTypeJson: boolean = false): HeadersInit {
  const headers = new Headers();
  if (contentTypeJson) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

function adminFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return fetch(input, { ...init, credentials: "include" });
}

export async function listEstabelecimentosAdmin(): Promise<EstabelecimentoAdmin[]> {
  const res = await adminFetch(`${API_URL}/estabelecimentos/`, {
    cache: "no-store",
    headers: getAdminHeaders(),
  });
  const data = (await parseOrThrow(res, "Falha ao carregar estabelecimentos.")) as EstabelecimentoApi[];
  return data.map(toUi);
}

export async function listPaymentEstablishmentsAdmin(): Promise<AdminPaymentEstablishment[]> {
  const res = await adminFetch(`${API_URL}/admin/establishments`, {
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
  const res = await adminFetch(`${API_URL}/estabelecimentos/`, {
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
  const res = await adminFetch(`${API_URL}/estabelecimentos/${id}`, {
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
  const res = await adminFetch(`${API_URL}/estabelecimentos/${id}`, {
    method: "DELETE",
    headers: getAdminHeaders(),
  });
  await parseOrThrow(res, "Falha ao excluir estabelecimento.");
}

export async function getPaymentAccountAdmin(establishmentId: number): Promise<AdminPaymentAccount | null> {
  const res = await adminFetch(`${API_URL}/admin/establishments/${establishmentId}/payment-account`, {
    cache: "no-store",
    headers: getAdminHeaders(),
  });
  if (res.status === 404) return null;
  return parseOrThrow(res, "Falha ao carregar conta de pagamento.");
}

<<<<<<< HEAD
export async function getMercadoPagoIntegrationAdmin(establishmentId: number): Promise<AdminPaymentIntegration | null> {
  const res = await adminFetch(`${API_URL}/admin/establishments/${establishmentId}/payment-integrations`, {
    cache: "no-store",
    headers: getAdminHeaders(),
  });
  const integrations = (await parseOrThrow(res, "Falha ao carregar integracoes de pagamento.")) as AdminPaymentIntegration[];
  return integrations.find((item) => item.provider === "mercadopago") ?? null;
}

export async function saveMercadoPagoIntegrationAdmin(
  establishmentId: number,
  payload: {
    environment: "sandbox" | "production";
    public_key?: string | null;
    access_token?: string | null;
    client_id?: string | null;
    client_secret?: string | null;
    webhook_secret?: string | null;
    notes?: string | null;
    status?: "active" | "inactive" | "error" | "pending_validation" | "disconnected";
  },
  exists: boolean,
): Promise<AdminPaymentIntegration> {
  const res = await adminFetch(`${API_URL}/admin/establishments/${establishmentId}/payment-integrations/mercado-pago`, {
    method: exists ? "PATCH" : "POST",
    headers: getAdminHeaders(true),
    body: JSON.stringify(payload),
  });
  return parseOrThrow(res, "Falha ao salvar credenciais Mercado Pago.");
}

export async function clearMercadoPagoIntegrationFieldAdmin(
  establishmentId: number,
  environment: "sandbox" | "production",
  field: "public_key" | "client_id" | "client_secret" | "webhook_secret" | "notes",
): Promise<AdminPaymentIntegration> {
  const clearFlagByField = {
    public_key: "clear_public_key",
    client_id: "clear_client_id",
    client_secret: "clear_client_secret",
    webhook_secret: "clear_webhook_secret",
    notes: "clear_notes",
  } as const;
  const res = await adminFetch(`${API_URL}/admin/establishments/${establishmentId}/payment-integrations/mercado-pago`, {
    method: "PATCH",
    headers: getAdminHeaders(true),
    body: JSON.stringify({
      environment,
      [clearFlagByField[field]]: true,
    }),
  });
  return parseOrThrow(res, "Falha ao limpar campo da integracao Mercado Pago.");
}

export async function disableMercadoPagoIntegrationAdmin(
  establishmentId: number,
  environment: "sandbox" | "production",
): Promise<AdminPaymentIntegration> {
  const res = await adminFetch(`${API_URL}/admin/establishments/${establishmentId}/payment-integrations/mercado-pago/disable`, {
    method: "POST",
    headers: getAdminHeaders(true),
    body: JSON.stringify({ environment, status: "inactive" }),
  });
  return parseOrThrow(res, "Falha ao desativar integracao Mercado Pago.");
}

export async function validateMercadoPagoIntegrationAdmin(
  establishmentId: number,
  environment: "sandbox" | "production",
): Promise<AdminPaymentIntegrationValidation> {
  const res = await adminFetch(`${API_URL}/admin/establishments/${establishmentId}/payment-integrations/mercado-pago/validate`, {
    method: "POST",
    headers: getAdminHeaders(true),
    body: JSON.stringify({ environment }),
  });
  return parseOrThrow(res, "Falha ao validar integracao Mercado Pago.");
}

export async function testMercadoPagoCheckoutAdmin(
  establishmentId: number,
  environment: "sandbox" | "production",
  confirmProduction: boolean,
): Promise<AdminPaymentIntegrationTestCheckout> {
  const res = await adminFetch(`${API_URL}/admin/establishments/${establishmentId}/payment-integrations/mercado-pago/test-checkout`, {
    method: "POST",
    headers: getAdminHeaders(true),
    body: JSON.stringify({ environment, confirm_production: confirmProduction }),
  });
  return parseOrThrow(res, "Falha ao criar checkout de teste Mercado Pago.");
}

export async function savePaymentAccountAdmin(
  establishmentId: number,
  payload: {
    account_name?: string | null;
    environment: "sandbox" | "production";
    client_id?: string | null;
    client_secret?: string | null;
    access_token?: string | null;
    public_key?: string | null;
    webhook_secret?: string | null;
    status: "active" | "inactive" | "error" | "pending_validation" | "disconnected";
    internal_notes?: string | null;
    checkout_hold_minutes: number;
  },
  exists: boolean,
): Promise<AdminPaymentAccount> {
  const res = await adminFetch(`${API_URL}/admin/establishments/${establishmentId}/payment-account`, {
    method: exists ? "PATCH" : "POST",
    headers: getAdminHeaders(true),
    body: JSON.stringify({
      provider: "mercadopago",
      ...payload,
    }),
=======
export async function deactivatePaymentAccountAdmin(establishmentId: number): Promise<AdminPaymentAccount> {
  const res = await fetch(`${API_URL}/admin/establishments/${establishmentId}/payment-account/deactivate`, {
    method: "POST",
    headers: getAdminHeaders(),
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
  });
  return parseOrThrow(res, "Falha ao desativar integracao de pagamento.");
}

<<<<<<< HEAD
export async function updatePaymentAccountStatusAdmin(
  establishmentId: number,
  status: "active" | "inactive" | "error" | "revoked" | "disconnected" | "pending_validation",
  environment: "sandbox" | "production" = "production",
): Promise<AdminPaymentAccount> {
  const res = await adminFetch(`${API_URL}/admin/establishments/${establishmentId}/payment-account/status`, {
    method: "PATCH",
    headers: getAdminHeaders(true),
    body: JSON.stringify({ status, environment }),
=======
export async function requestPaymentReconnectAdmin(establishmentId: number): Promise<AdminPaymentAccount> {
  const res = await fetch(`${API_URL}/admin/establishments/${establishmentId}/payment-account/request-reconnect`, {
    method: "POST",
    headers: getAdminHeaders(),
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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
