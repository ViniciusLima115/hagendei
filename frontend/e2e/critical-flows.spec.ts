import { expect, Page, Route, test } from "@playwright/test";

const API_ORIGIN = "http://127.0.0.1:8000";
const APP_ORIGIN = "http://127.0.0.1:3100";

const corsHeaders = {
  "Access-Control-Allow-Origin": APP_ORIGIN,
  "Access-Control-Allow-Credentials": "true",
  "Access-Control-Allow-Headers": "Content-Type,X-Estabelecimento-Id",
  "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  if (route.request().method() === "OPTIONS") {
    await route.fulfill({ status: 204, headers: corsHeaders });
    return;
  }
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: corsHeaders,
    body: JSON.stringify(body),
  });
}

async function mockLoginApi(page: Page) {
  await page.route(`${API_ORIGIN}/**`, async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === "OPTIONS") {
      await fulfillJson(route, null);
      return;
    }
    if (url.pathname === "/auth/login") {
      await fulfillJson(route, {
        is_admin: false,
        tenant_id: 42,
        tenant_name: "Fluxo E2E",
        plano: "gratis",
        token_type: "bearer",
      });
      return;
    }
    if (url.pathname === "/auth/me") {
      await fulfillJson(route, {
        id: 42,
        nome: "Fluxo E2E",
        plano: "gratis",
        is_admin: false,
        accent_color: "#7c3aed",
        bg_color: "#f8fafc",
      });
      return;
    }
    if (
      url.pathname === "/notificacoes" ||
      url.pathname === "/agendamentos/" ||
      url.pathname === "/clientes/" ||
      url.pathname === "/servicos/" ||
      url.pathname === "/profissionais/"
    ) {
      await fulfillJson(route, []);
      return;
    }
    if (url.pathname === "/agenda/dia") {
      await fulfillJson(route, { horarios: [], barbeiros: [] });
      return;
    }
    await fulfillJson(route, {});
  });
}

test("rota privada redireciona visitante para o login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?next=%2Fdashboard$/);
  await expect(page.getByRole("heading", { name: "Bem-vindo de volta." })).toBeVisible();
});

test("login de tenant mantém plano grátis e identidade visual na sessão", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await mockLoginApi(page);
  await page.goto("/login");

  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByText("Preencha todos os campos para entrar.")).toBeVisible();

  await page.getByLabel("Usuário").fill("e2e@hagendei.test");
  await page.locator("#password").fill("Senha-E2E-123!");
  await page.getByRole("button", { name: "Entrar" }).click();

  await expect(page).toHaveURL("/");
  const session = await page.evaluate(() => {
    const raw = localStorage.getItem("hagendei_auth_session");
    return raw ? JSON.parse(raw) : null;
  });
  expect(session).toMatchObject({
    tenantId: "42",
    tenantName: "Fluxo E2E",
    plan: "gratis",
    accentColor: "#7c3aed",
    bgColor: "#f8fafc",
  });
  expect(pageErrors).toEqual([]);
});

test("agendamento público valida contato, aplica tema e envia payload correto", async ({ page }) => {
  const lookup = {
    estabelecimento_id: 42,
    nome: "Clínica Fluxo E2E",
    slug: "fluxo-e2e",
    accent_color: "#7c3aed",
    bg_color: "#f8fafc",
    logo_url: null,
    barbeiros: [{ id: 7, nome: "Ana" }],
    servicos: [{ id: 9, nome: "Consulta", duracao: 30, preco: 80 }],
    horarios_disponiveis: ["10:00"],
    horarios_grade: [{ hora: "10:00", disponivel: true }],
  };
  let postedPayload: Record<string, unknown> | null = null;

  await page.route(`${API_ORIGIN}/**`, async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === "OPTIONS") {
      await fulfillJson(route, null);
      return;
    }
    if (url.pathname === "/public/estabelecimento/fluxo-e2e") {
      await fulfillJson(route, lookup);
      return;
    }
    if (url.pathname === "/public/agendamentos" && route.request().method() === "POST") {
      postedPayload = route.request().postDataJSON();
      await fulfillJson(route, {
        id: 123,
        tenant_id: 42,
        estabelecimento_id: 42,
        slug: "fluxo-e2e",
        cliente_nome: "Maria da Silva",
        cliente_telefone: "11987654321",
        cliente_email: "maria@example.com",
        barbeiro_id: 7,
        servico_id: 9,
        data_hora_inicio: "2030-01-01T10:00:00",
        data_hora_fim: "2030-01-01T10:30:00",
        status: "pendente",
        confirmation_token: "token-e2e",
        lembretes_agendados: 2,
      });
      return;
    }
    await fulfillJson(route, { detail: "Rota não simulada." }, 404);
  });

  await page.goto("/fluxo-e2e");
  await expect(page.getByRole("heading", { name: "Clínica Fluxo E2E" })).toBeVisible();
  const theme = await page.locator("main").evaluate((element) => ({
    accent: (element as HTMLElement).style.getPropertyValue("--accent"),
    background: (element as HTMLElement).style.getPropertyValue("--bg-tenant"),
  }));
  expect(theme).toEqual({ accent: "#7c3aed", background: "#f8fafc" });

  await page.getByRole("button", { name: /10:00 - disponível/i }).click();
  await page.getByLabel("Nome completo").fill("Maria da Silva");
  await page.getByLabel("Telefone (WhatsApp)").fill("1");
  await page.getByLabel("E-mail").fill("maria@example.com");
  await page.getByRole("button", { name: "Confirmar agendamento" }).click();
  expect(postedPayload).toBeNull();

  await page.getByLabel("Telefone (WhatsApp)").fill("11987654321");
  await page.getByRole("button", { name: "Confirmar agendamento" }).click();
  await expect(page.getByText("Agendamento criado. Enviamos a confirmação por e-mail.")).toBeVisible();
  expect(postedPayload).toMatchObject({
    slug: "fluxo-e2e",
    cliente_nome: "Maria da Silva",
    cliente_telefone: "11987654321",
    cliente_email: "maria@example.com",
    barbeiro_id: 7,
    servico_id: 9,
    hora_inicio: "10:00",
  });
});

test("erro 422 da API pública é exibido de forma legível", async ({ page }) => {
  const lookup = {
    estabelecimento_id: 42,
    nome: "Clínica Fluxo E2E",
    slug: "fluxo-e2e",
    barbeiros: [{ id: 7, nome: "Ana" }],
    servicos: [{ id: 9, nome: "Consulta", duracao: 30, preco: 80 }],
    horarios_disponiveis: ["10:00"],
    horarios_grade: [{ hora: "10:00", disponivel: true }],
  };
  await page.route(`${API_ORIGIN}/**`, async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === "OPTIONS") {
      await fulfillJson(route, null);
      return;
    }
    if (url.pathname === "/public/estabelecimento/fluxo-e2e") {
      await fulfillJson(route, lookup);
      return;
    }
    if (url.pathname === "/public/agendamentos") {
      await fulfillJson(
        route,
        {
          detail: [
            {
              loc: ["body", "cliente_telefone"],
              msg: "Telefone inválido.",
              type: "value_error",
            },
          ],
        },
        422,
      );
      return;
    }
    await fulfillJson(route, {}, 404);
  });

  await page.goto("/fluxo-e2e");
  await page.getByRole("button", { name: /10:00 - disponível/i }).click();
  await page.getByLabel("Nome completo").fill("Maria da Silva");
  await page.getByLabel("Telefone (WhatsApp)").fill("11987654321");
  await page.getByLabel("E-mail").fill("maria@example.com");
  await page.getByRole("button", { name: "Confirmar agendamento" }).click();

  await expect(
    page.getByRole("alert").getByText("cliente_telefone: Telefone inválido."),
  ).toBeVisible();
  await expect(page.getByText("[object Object]")).toHaveCount(0);
});

test("reagendamento envia o novo profissional e o novo serviço", async ({ page }) => {
  const today = new Date().toISOString().slice(0, 10);
  let putPayload: Record<string, unknown> | null = null;
  const booking = {
    id: 123,
    estabelecimento_id: 42,
    slug: "fluxo-e2e",
    confirmation_token: "token-e2e",
    cliente_nome: "Maria da Silva",
    cliente_email: "maria@example.com",
    barbeiro_id: 7,
    barbeiro_nome: "Ana",
    servico_id: 9,
    servico_nome: "Consulta",
    data_hora_inicio: `${today}T09:00:00`,
    data_hora_fim: `${today}T09:30:00`,
    status: "reagendamento_solicitado",
  };
  const lookup = {
    estabelecimento_id: 42,
    nome: "Clínica Fluxo E2E",
    slug: "fluxo-e2e",
    barbeiros: [
      { id: 7, nome: "Ana" },
      { id: 8, nome: "Bruno" },
    ],
    servicos: [
      { id: 9, nome: "Consulta", duracao: 30, preco: 80 },
      { id: 10, nome: "Retorno", duracao: 45, preco: 100 },
    ],
    horarios_disponiveis: ["11:00"],
    horarios_grade: [{ hora: "11:00", disponivel: true }],
  };

  await page.route(`${API_ORIGIN}/**`, async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === "OPTIONS") {
      await fulfillJson(route, null);
      return;
    }
    if (url.pathname === "/agendamentos/token-e2e/dados") {
      await fulfillJson(route, booking);
      return;
    }
    if (url.pathname === "/public/estabelecimento-id/42") {
      await fulfillJson(route, lookup);
      return;
    }
    if (
      url.pathname === "/agendamentos/token-e2e/remarcar" &&
      route.request().method() === "PUT"
    ) {
      putPayload = route.request().postDataJSON();
      await fulfillJson(route, {
        ...booking,
        barbeiro_id: 8,
        barbeiro_nome: "Bruno",
        servico_id: 10,
        servico_nome: "Retorno",
        data_hora_inicio: `${today}T11:00:00`,
        data_hora_fim: `${today}T11:45:00`,
        status: "confirmado",
      });
      return;
    }
    await fulfillJson(route, {}, 404);
  });

  await page.goto("/reagendar/token-e2e");
  await page.getByLabel("Profissional").selectOption("8");
  await page.getByLabel("Serviço").selectOption("10");
  await page.getByRole("button", { name: /11:00/ }).click();
  await page.getByRole("button", { name: "Confirmar novo horário" }).click();

  await expect(page.getByText("Agendamento reagendado com sucesso!")).toBeVisible();
  expect(putPayload).toMatchObject({
    barbeiro_id: 8,
    servico_id: 10,
    data_hora_inicio: `${today}T11:00:00`,
  });
});
