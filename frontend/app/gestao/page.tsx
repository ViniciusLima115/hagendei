"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Agendamento,
  Barbeiro,
  Cliente,
  Servico,
  createAgendamento,
  createCliente,
  createServico,
  deleteAgendamento,
  deleteCliente,
  deleteServico,
  listAgendamentos,
  listBarbeiros,
  listClientes,
  listServicos,
  updateAgendamento,
  updateCliente,
  updateServico,
} from "@/services/api";

type Tab = "agendamentos" | "clientes" | "servicos";

const initialCliente = { nome: "", telefone: "" };
const initialServico = { nome: "", duracao_minutos: 40, preco: 40 };

function toBackendDateTime(localValue: string): string {
  // Mantem horário local selecionado no input datetime-local, sem converter para UTC.
  return `${localValue}:00`;
}

function toDateTimeLocalInput(value: string): string {
  const date = new Date(value);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const h = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d}T${h}:${min}`;
}

export default function GestaoPage() {
  const [tab, setTab] = useState<Tab>("agendamentos");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [servicos, setServicos] = useState<Servico[]>([]);
  const [barbeiros, setBarbeiros] = useState<Barbeiro[]>([]);
  const [agendamentos, setAgendamentos] = useState<Agendamento[]>([]);

  const [novoCliente, setNovoCliente] = useState(initialCliente);
  const [editClienteId, setEditClienteId] = useState<number | null>(null);

  const [novoServico, setNovoServico] = useState(initialServico);
  const [editServicoId, setEditServicoId] = useState<number | null>(null);

  const [formAgendamento, setFormAgendamento] = useState({
    clienteId: "",
    barbeiroId: "",
    servicoId: "",
    dataHora: "",
    status: "confirmado" as "pendente" | "confirmado" | "cancelado",
  });
  const [editAgendamentoId, setEditAgendamentoId] = useState<number | null>(null);

  async function carregarTudo() {
    setLoading(true);
    setError(null);
    try {
      const [cs, ss, bs, as] = await Promise.all([
        listClientes(),
        listServicos(),
        listBarbeiros(),
        listAgendamentos(),
      ]);
      setClientes(cs);
      setServicos(ss);
      setBarbeiros(bs);
      setAgendamentos(as);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar dados.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    carregarTudo();
  }, []);

  useEffect(() => {
    if (!success) return;
    const t = setTimeout(() => setSuccess(null), 3000);
    return () => clearTimeout(t);
  }, [success]);

  const clientesById = useMemo(
    () => Object.fromEntries(clientes.map((c) => [c.id, c])),
    [clientes]
  );

  const limparMensagens = () => {
    setError(null);
    setSuccess(null);
  };

  async function submitCliente(e: FormEvent) {
    e.preventDefault();
    limparMensagens();
    try {
      if (editClienteId) {
        await updateCliente(editClienteId, { ...novoCliente, etapa_atual: "menu" });
        setSuccess("Cliente atualizado.");
      } else {
        await createCliente({ ...novoCliente, etapa_atual: "menu" });
        setSuccess("Cliente criado.");
      }
      setNovoCliente(initialCliente);
      setEditClienteId(null);
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar cliente.");
    }
  }

  async function submitServico(e: FormEvent) {
    e.preventDefault();
    limparMensagens();
    try {
      if (editServicoId) {
        await updateServico(editServicoId, novoServico);
        setSuccess("Serviço atualizado.");
      } else {
        await createServico(novoServico);
        setSuccess("Serviço criado.");
      }
      setNovoServico(initialServico);
      setEditServicoId(null);
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar serviço.");
    }
  }

  async function submitAgendamento(e: FormEvent) {
    e.preventDefault();
    limparMensagens();

    const cliente = clientesById[Number(formAgendamento.clienteId)];
    if (!cliente) {
      setError("Selecione um cliente válido.");
      return;
    }

    try {
      if (editAgendamentoId) {
        await updateAgendamento(editAgendamentoId, {
          barbeiro_id: Number(formAgendamento.barbeiroId),
          servico_id: Number(formAgendamento.servicoId),
          data_hora_inicio: toBackendDateTime(formAgendamento.dataHora),
          status: formAgendamento.status,
        });
        setSuccess("Agendamento atualizado.");
      } else {
        await createAgendamento({
          telefone: cliente.telefone,
          nome_cliente: cliente.nome,
          barbeiro_id: Number(formAgendamento.barbeiroId),
          servico_id: Number(formAgendamento.servicoId),
          data_hora_inicio: toBackendDateTime(formAgendamento.dataHora),
          status: formAgendamento.status,
        });
        setSuccess("Agendamento criado.");
      }
      setFormAgendamento({
        clienteId: "",
        barbeiroId: "",
        servicoId: "",
        dataHora: "",
        status: "confirmado",
      });
      setEditAgendamentoId(null);
      await carregarTudo();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar agendamento.");
    }
  }

  return (
    <main className="px-4 py-6 md:px-8">
      <section className="glass-panel mx-auto max-w-7xl rounded-2xl p-6 md:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-zinc-500">Administração</p>
            <h1 className="mt-2 text-3xl font-black uppercase tracking-tight">Gestão da Barbearia</h1>
            <p className="mt-2 text-sm text-zinc-600">Cadastre, edite e remova agendamentos, clientes e serviços em um único painel.</p>
          </div>
          <button
            type="button"
            onClick={carregarTudo}
            className="rounded-xl border border-[var(--line-strong)] bg-[var(--surface)] px-4 py-2 text-sm font-semibold"
          >
            Atualizar dados
          </button>
        </div>

        <div className="mt-6 flex flex-wrap gap-2">
          {([
            ["agendamentos", "Agendamentos"],
            ["clientes", "Clientes"],
            ["servicos", "Serviços"],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                tab === key
                  ? "bg-[var(--accent)] text-white"
                  : "border border-[var(--line)] bg-[var(--surface)]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {loading && <p className="mt-4 text-sm text-zinc-600">Carregando...</p>}
        {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-[var(--danger)]">{error}</p>}
        {success && <p className="mt-4 rounded-lg bg-emerald-50 p-3 text-sm text-[var(--ok)]">{success}</p>}

        {tab === "clientes" && (
          <div className="mt-6 grid gap-6 lg:grid-cols-[360px_1fr]">
            <form onSubmit={submitCliente} className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-4 space-y-3">
              <h2 className="text-sm font-bold uppercase">{editClienteId ? "Editar cliente" : "Novo cliente"}</h2>
              <input
                required
                placeholder="Nome"
                value={novoCliente.nome}
                onChange={(e) => setNovoCliente((p) => ({ ...p, nome: e.target.value }))}
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              />
              <input
                required
                placeholder="Telefone"
                value={novoCliente.telefone}
                onChange={(e) => setNovoCliente((p) => ({ ...p, telefone: e.target.value }))}
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              />
              <div className="flex gap-2">
                <button type="submit" className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white">
                  {editClienteId ? "Salvar" : "Adicionar"}
                </button>
                {editClienteId && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditClienteId(null);
                      setNovoCliente(initialCliente);
                    }}
                    className="rounded-lg border border-[var(--line)] px-4 py-2 text-sm"
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </form>

            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-4">
              <h3 className="text-sm font-bold uppercase">Clientes</h3>
              <div className="mt-3 overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="text-zinc-500">
                      <th className="pb-2">Nome</th>
                      <th className="pb-2">Telefone</th>
                      <th className="pb-2">Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clientes.map((c) => (
                      <tr key={c.id} className="border-t border-[var(--line)]">
                        <td className="py-2">{c.nome}</td>
                        <td className="py-2">{c.telefone}</td>
                        <td className="py-2">
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setEditClienteId(c.id);
                                setNovoCliente({ nome: c.nome, telefone: c.telefone });
                              }}
                              className="rounded-md border border-[var(--line)] px-2 py-1 text-xs"
                            >
                              Editar
                            </button>
                            <button
                              type="button"
                              onClick={async () => {
                                try {
                                  limparMensagens();
                                  await deleteCliente(c.id);
                                  setSuccess("Cliente removido.");
                                  await carregarTudo();
                                } catch (e) {
                                  setError(e instanceof Error ? e.message : "Erro ao remover cliente.");
                                }
                              }}
                              className="rounded-md bg-red-100 px-2 py-1 text-xs text-[var(--danger)]"
                            >
                              Remover
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {tab === "servicos" && (
          <div className="mt-6 grid gap-6 lg:grid-cols-[360px_1fr]">
            <form onSubmit={submitServico} className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-4 space-y-3">
              <h2 className="text-sm font-bold uppercase">{editServicoId ? "Editar serviço" : "Novo serviço"}</h2>
              <input
                required
                placeholder="Nome"
                value={novoServico.nome}
                onChange={(e) => setNovoServico((p) => ({ ...p, nome: e.target.value }))}
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              />
              <input
                required
                type="number"
                placeholder="Duração (min)"
                value={novoServico.duracao_minutos}
                onChange={(e) => setNovoServico((p) => ({ ...p, duracao_minutos: Number(e.target.value) }))}
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              />
              <input
                required
                type="number"
                step="0.01"
                placeholder="Preço"
                value={novoServico.preco}
                onChange={(e) => setNovoServico((p) => ({ ...p, preco: Number(e.target.value) }))}
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              />
              <div className="flex gap-2">
                <button type="submit" className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white">
                  {editServicoId ? "Salvar" : "Adicionar"}
                </button>
                {editServicoId && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditServicoId(null);
                      setNovoServico(initialServico);
                    }}
                    className="rounded-lg border border-[var(--line)] px-4 py-2 text-sm"
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </form>

            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-4">
              <h3 className="text-sm font-bold uppercase">Serviços</h3>
              <div className="mt-3 overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="text-zinc-500">
                      <th className="pb-2">Nome</th>
                      <th className="pb-2">Duração</th>
                      <th className="pb-2">Preço</th>
                      <th className="pb-2">Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {servicos.map((s) => (
                      <tr key={s.id} className="border-t border-[var(--line)]">
                        <td className="py-2">{s.nome}</td>
                        <td className="py-2">{s.duracao_minutos} min</td>
                        <td className="py-2">R$ {s.preco.toFixed(2)}</td>
                        <td className="py-2">
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setEditServicoId(s.id);
                                setNovoServico({
                                  nome: s.nome,
                                  duracao_minutos: s.duracao_minutos,
                                  preco: s.preco,
                                });
                              }}
                              className="rounded-md border border-[var(--line)] px-2 py-1 text-xs"
                            >
                              Editar
                            </button>
                            <button
                              type="button"
                              onClick={async () => {
                                try {
                                  limparMensagens();
                                  await deleteServico(s.id);
                                  setSuccess("Serviço removido.");
                                  await carregarTudo();
                                } catch (e) {
                                  setError(e instanceof Error ? e.message : "Erro ao remover serviço.");
                                }
                              }}
                              className="rounded-md bg-red-100 px-2 py-1 text-xs text-[var(--danger)]"
                            >
                              Remover
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {tab === "agendamentos" && (
          <div className="mt-6 grid gap-6 lg:grid-cols-[420px_1fr]">
            <form onSubmit={submitAgendamento} className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-4 space-y-3">
              <h2 className="text-sm font-bold uppercase">{editAgendamentoId ? "Editar agendamento" : "Novo agendamento"}</h2>
              <select
                required
                value={formAgendamento.clienteId}
                onChange={(e) => setFormAgendamento((p) => ({ ...p, clienteId: e.target.value }))}
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              >
                <option value="">Selecione o cliente</option>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome} ({c.telefone})
                  </option>
                ))}
              </select>
              <select
                required
                value={formAgendamento.barbeiroId}
                onChange={(e) => setFormAgendamento((p) => ({ ...p, barbeiroId: e.target.value }))}
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              >
                <option value="">Selecione o barbeiro</option>
                {barbeiros.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.nome}
                  </option>
                ))}
              </select>
              <select
                required
                value={formAgendamento.servicoId}
                onChange={(e) => setFormAgendamento((p) => ({ ...p, servicoId: e.target.value }))}
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              >
                <option value="">Selecione o serviço</option>
                {servicos.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nome}
                  </option>
                ))}
              </select>
              <input
                required
                type="datetime-local"
                value={formAgendamento.dataHora}
                onChange={(e) => setFormAgendamento((p) => ({ ...p, dataHora: e.target.value }))}
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              />
              <select
                value={formAgendamento.status}
                onChange={(e) =>
                  setFormAgendamento((p) => ({
                    ...p,
                    status: e.target.value as "pendente" | "confirmado" | "cancelado",
                  }))
                }
                className="w-full rounded-lg border border-[var(--line)] px-3 py-2"
              >
                <option value="confirmado">Confirmado</option>
                <option value="pendente">Pendente</option>
                <option value="cancelado">Cancelado</option>
              </select>
              <div className="flex gap-2">
                <button type="submit" className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white">
                  {editAgendamentoId ? "Salvar" : "Adicionar"}
                </button>
                {editAgendamentoId && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditAgendamentoId(null);
                      setFormAgendamento({
                        clienteId: "",
                        barbeiroId: "",
                        servicoId: "",
                        dataHora: "",
                        status: "confirmado",
                      });
                    }}
                    className="rounded-lg border border-[var(--line)] px-4 py-2 text-sm"
                  >
                    Cancelar
                  </button>
                )}
              </div>
            </form>

            <div className="rounded-xl border border-[var(--line)] bg-[var(--surface)] p-4">
              <h3 className="text-sm font-bold uppercase">Agendamentos</h3>
              <div className="mt-3 overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="text-zinc-500">
                      <th className="pb-2">Cliente</th>
                      <th className="pb-2">Serviço</th>
                      <th className="pb-2">Horário</th>
                      <th className="pb-2">Status</th>
                      <th className="pb-2">Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agendamentos.map((a) => (
                      <tr key={a.id} className="border-t border-[var(--line)]">
                        <td className="py-2">{a.cliente_nome}</td>
                        <td className="py-2">{a.servico_nome}</td>
                        <td className="py-2">{new Date(a.data_hora_inicio).toLocaleString("pt-BR")}</td>
                        <td className="py-2 capitalize">{a.status}</td>
                        <td className="py-2">
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                const cliente = clientes.find((c) => c.telefone === a.telefone);
                                const barbeiro = barbeiros.find((b) => b.nome === a.barbeiro_nome);
                                const servico = servicos.find((s) => s.nome === a.servico_nome);
                                setEditAgendamentoId(a.id);
                                setFormAgendamento({
                                  clienteId: cliente ? String(cliente.id) : "",
                                  barbeiroId: barbeiro ? String(barbeiro.id) : "",
                                  servicoId: servico ? String(servico.id) : "",
                                  dataHora: toDateTimeLocalInput(a.data_hora_inicio),
                                  status: a.status,
                                });
                              }}
                              className="rounded-md border border-[var(--line)] px-2 py-1 text-xs"
                            >
                              Editar
                            </button>
                            <button
                              type="button"
                              onClick={async () => {
                                try {
                                  limparMensagens();
                                  await deleteAgendamento(a.id);
                                  setSuccess("Agendamento removido.");
                                  await carregarTudo();
                                } catch (e) {
                                  setError(e instanceof Error ? e.message : "Erro ao remover agendamento.");
                                }
                              }}
                              className="rounded-md bg-red-100 px-2 py-1 text-xs text-[var(--danger)]"
                            >
                              Remover
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
