"use client";

import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Check,
  CircleAlert,
  Clock3,
  CreditCard,
  ExternalLink,
  LoaderCircle,
  Mail,
  Scissors,
  ShieldCheck,
  Smartphone,
  UserRound,
  UsersRound,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  AlertCircle,
  CalendarCheck,
  CalendarDays,
  Check,
  CheckCircle2,
  ClipboardList,
  Clock3,
  CreditCard,
  LoaderCircle,
  Mail,
  MessageCircle,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import {
  createPublicBooking,
  lookupPublicBarbershop,
  PublicLookupResponse,
  startPublicBookingPayment,
} from "@/services/api";
import styles from "./page.module.css";

function hojeISO() {
  const agora = new Date();
  const local = new Date(agora.getTime() - agora.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function moedaBRL(valor: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(valor);
}

function normalizarTelefone(valor: string) {
  return valor.replace(/\D/g, "");
}

<<<<<<< HEAD
function formatarTelefone(valor: string) {
  const numeros = normalizarTelefone(valor).slice(0, 11);
  if (numeros.length <= 2) return numeros;
  if (numeros.length <= 7) return `(${numeros.slice(0, 2)}) ${numeros.slice(2)}`;
  if (numeros.length <= 10) {
    return `(${numeros.slice(0, 2)}) ${numeros.slice(2, 6)}-${numeros.slice(6)}`;
  }
  return `(${numeros.slice(0, 2)}) ${numeros.slice(2, 7)}-${numeros.slice(7)}`;
}

function formatarData(data: string) {
  const [ano, mes, dia] = data.split("-").map(Number);
  if (!ano || !mes || !dia) return "-";
=======
function formatarData(valor: string) {
  if (!valor) return "-";
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
  return new Intl.DateTimeFormat("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "short",
<<<<<<< HEAD
  }).format(new Date(ano, mes - 1, dia));
=======
  }).format(new Date(`${valor}T12:00:00`));
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
}

export default function PublicBookingPage() {
  const params = useParams<{ slug: string }>();
  const slug = (params?.slug || "").trim().toLowerCase();

  const [loading, setLoading] = useState(true);
  const [loadingHorarios, setLoadingHorarios] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [lookup, setLookup] = useState<PublicLookupResponse | null>(null);
  const [showPaymentNotice, setShowPaymentNotice] = useState(false);

  const [nomeCliente, setNomeCliente] = useState("");
  const [telefoneCliente, setTelefoneCliente] = useState("");
  const [emailCliente, setEmailCliente] = useState("");
  const [barbeiroId, setBarbeiroId] = useState<number | null>(null);
  const [servicoId, setServicoId] = useState<number | null>(null);
  const [data, setData] = useState(hojeISO());
  const [horaInicio, setHoraInicio] = useState<string | null>(null);

  useEffect(() => {
    let ativo = true;

    async function carregarInicial() {
      if (!slug) return;
      setLoading(true);
      setErro(null);
      try {
        const base = await lookupPublicBarbershop({ slug });
        if (!ativo) return;
        setLookup(base);
        setBarbeiroId(base.barbeiros[0]?.id ?? null);
        setServicoId(base.servicos[0]?.id ?? null);
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Não foi possível carregar o estabelecimento.");
      } finally {
        if (ativo) setLoading(false);
      }
    }

    carregarInicial();
    return () => {
      ativo = false;
    };
  }, [slug]);

  useEffect(() => {
    let ativo = true;

    async function carregarDisponibilidade() {
      if (!slug || !barbeiroId || !servicoId) return;
      setLoadingHorarios(true);
      setErro(null);
      try {
        const atualizado = await lookupPublicBarbershop({
          slug,
          data,
          barbeiro_id: barbeiroId,
          servico_id: servicoId,
        });
        if (!ativo) return;
        setLookup(atualizado);
        setHoraInicio((horaAtual) => {
          if (!horaAtual) return horaAtual;
          const aindaDisponivel = atualizado.horarios_grade.some(
            (slot) => slot.hora === horaAtual && slot.disponivel,
          );
          return aindaDisponivel ? horaAtual : null;
        });
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Falha ao carregar horários.");
<<<<<<< HEAD
      } finally {
        if (ativo) setLoadingHorarios(false);
=======
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
      }
    }

    carregarDisponibilidade();
    return () => {
      ativo = false;
    };
  }, [slug, barbeiroId, servicoId, data]);

  useEffect(() => {
    if (!showPaymentNotice) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !submitting) {
        setShowPaymentNotice(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [showPaymentNotice, submitting]);

  const servicoSelecionado = useMemo(() => {
    if (!lookup || !servicoId) return null;
    return lookup.servicos.find((item) => item.id === servicoId) ?? null;
  }, [lookup, servicoId]);

  const barbeiroSelecionado = useMemo(() => {
    if (!lookup || !barbeiroId) return null;
    return lookup.barbeiros.find((item) => item.id === barbeiroId) ?? null;
  }, [lookup, barbeiroId]);

  const pagamentoAdiantadoObrigatorio = Boolean(
    servicoSelecionado?.pagamento_adiantado_obrigatorio_efetivo
  );
  const tipoPagamentoAdiantado = servicoSelecionado?.advance_payment_type ?? "full";
  const valorPagamentoAdiantado =
    tipoPagamentoAdiantado === "signal"
      ? Number(servicoSelecionado?.advance_payment_amount || 0)
      : Number(servicoSelecionado?.preco || 0);
<<<<<<< HEAD
  const dadosClientePreenchidos = Boolean(
    nomeCliente.trim() && normalizarTelefone(telefoneCliente) && emailCliente.trim()
  );
=======
  const horariosDisponiveis = lookup?.horarios_grade.filter((slot) => slot.disponivel).length ?? 0;
  const dataFormatada = formatarData(data);
  const podeConfirmar = Boolean(
    horaInicio
      && nomeCliente.trim()
      && normalizarTelefone(telefoneCliente)
      && emailCliente.trim()
      && barbeiroId
      && servicoId,
  );
  const valorParaConfirmar = servicoSelecionado
    ? pagamentoAdiantadoObrigatorio
      ? valorPagamentoAdiantado
      : servicoSelecionado.preco
    : 0;
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478

  function camposValidos() {
    if (!slug || !barbeiroId || !servicoId || !horaInicio) {
      setErro("Preencha todos os campos e selecione um horário disponível.");
<<<<<<< HEAD
      return;
    }
    if (!nomeCliente.trim() || !normalizarTelefone(telefoneCliente) || !emailCliente.trim()) {
      setErro("Preencha nome, telefone e e-mail.");
=======
      return false;
    }
    if (!nomeCliente.trim() || !normalizarTelefone(telefoneCliente) || !emailCliente.trim()) {
      setErro("Preencha nome, telefone e email.");
      return false;
    }
    return true;
  }

  async function concluirAgendamento() {
    if (!camposValidos() || !barbeiroId || !servicoId || !horaInicio) {
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
      return;
    }

    setSubmitting(true);
    setErro(null);
    setSucesso(null);
    try {
      const payload = {
        slug,
        cliente_nome: nomeCliente.trim(),
        cliente_telefone: normalizarTelefone(telefoneCliente),
        cliente_email: emailCliente.trim().toLowerCase(),
        barbeiro_id: barbeiroId,
        servico_id: servicoId,
        data,
        hora_inicio: horaInicio,
      };

      if (pagamentoAdiantadoObrigatorio) {
<<<<<<< HEAD
        setSucesso("Seu horário foi reservado por 5 minutos. Redirecionando para o checkout...");
=======
        setSucesso("Seu horário foi reservado. Redirecionando para o pagamento...");
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
        const pagamento = await startPublicBookingPayment(payload);
        window.location.href = pagamento.checkout_url;
        return;
      }

      await createPublicBooking(payload);
<<<<<<< HEAD
      setSucesso("Agendamento criado. Enviamos a confirmação por e-mail.");
=======
      setSucesso("Agendamento criado. Enviamos a confirmação por email.");
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
      setHoraInicio(null);

      const atualizado = await lookupPublicBarbershop({
        slug,
        data,
        barbeiro_id: barbeiroId,
        servico_id: servicoId,
      });
      setLookup(atualizado);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível concluir o agendamento.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!camposValidos()) return;

    if (pagamentoAdiantadoObrigatorio) {
      setErro(null);
      setShowPaymentNotice(true);
      return;
    }

    await concluirAgendamento();
  }

  if (loading) {
    return (
<<<<<<< HEAD
      <main className={styles.page}>
        <div className={styles.statePanel} role="status">
          <LoaderCircle className={styles.stateSpinner} size={24} aria-hidden="true" />
          <div>
            <strong>Preparando seu agendamento</strong>
            <p>Buscando profissionais, serviços e horários disponíveis.</p>
=======
      <main className="min-h-screen bg-[#f4f5f2] px-4 py-10">
        <div className="flex min-h-[55vh] items-center justify-center">
          <div className="flex items-center gap-3 text-sm font-semibold text-zinc-600">
            <LoaderCircle className="size-5 animate-spin text-emerald-700" />
            Carregando agenda...
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
          </div>
        </div>
      </main>
    );
  }

  if (!lookup) {
    return (
<<<<<<< HEAD
      <main className={styles.page}>
        <div className={styles.statePanel} role="alert">
          <AlertCircle size={24} aria-hidden="true" />
          <div>
            <strong>Página indisponível</strong>
            <p>{erro ?? "Estabelecimento não encontrado para este link."}</p>
          </div>
=======
      <main className="min-h-screen bg-[#f4f5f2] px-4 py-10">
        <div className="mx-auto max-w-xl rounded-lg border border-red-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-red-700">
            {erro ?? "Estabelecimento não encontrado para este link."}
          </p>
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
        </div>
      </main>
    );
  }

  return (
<<<<<<< HEAD
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.brandHeader}>
          <div className={styles.brandIdentity}>
            <span className={styles.brandMark} aria-hidden="true">
              <CalendarDays size={24} strokeWidth={2} />
            </span>
            <div>
              <p className={styles.eyebrow}>Agendamento online</p>
              <h1>{lookup.nome}</h1>
              <p className={styles.brandSubtitle}>Escolha o melhor horário para o seu atendimento.</p>
            </div>
          </div>
          <div className={styles.secureBadge}>
            <ShieldCheck size={17} aria-hidden="true" />
            <span>Reserva segura</span>
          </div>
        </header>

        <form className={styles.bookingLayout} onSubmit={onSubmit}>
          <div className={styles.formPanel}>
            <section className={styles.stepSection}>
              <div className={styles.stepHeader}>
                <span
                  className={`${styles.stepIndicator} ${
                    servicoSelecionado && barbeiroSelecionado ? styles.stepComplete : ""
                  }`}
                >
                  {servicoSelecionado && barbeiroSelecionado ? (
                    <Check size={17} aria-hidden="true" />
                  ) : (
                    "1"
                  )}
                </span>
                <div>
                  <h2>Escolha o atendimento</h2>
                  <p>Selecione o profissional e o serviço desejado.</p>
                </div>
              </div>

              <div className={styles.fieldGrid}>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Profissional</span>
                  <span className={styles.controlWrap}>
                    <UserRound size={18} aria-hidden="true" />
                    <select
                      className={styles.control}
                      value={barbeiroId ?? ""}
                      onChange={(event) => {
                        const valor = Number(event.target.value);
                        setBarbeiroId(Number.isFinite(valor) ? valor : null);
                        setHoraInicio(null);
                      }}
                    >
                      {lookup.barbeiros.map((barbeiro) => (
                        <option key={barbeiro.id} value={barbeiro.id}>
                          {barbeiro.nome}
                        </option>
                      ))}
                    </select>
                  </span>
                </label>

                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Serviço</span>
                  <span className={styles.controlWrap}>
                    <ClipboardList size={18} aria-hidden="true" />
                    <select
                      className={styles.control}
                      value={servicoId ?? ""}
                      onChange={(event) => {
                        const valor = Number(event.target.value);
                        setServicoId(Number.isFinite(valor) ? valor : null);
                        setHoraInicio(null);
                      }}
                    >
                      {lookup.servicos.map((servico) => (
                        <option key={servico.id} value={servico.id}>
                          {servico.nome} - {moedaBRL(servico.preco)}
                        </option>
                      ))}
                    </select>
                  </span>
                </label>
              </div>

              {servicoSelecionado ? (
                <div className={styles.serviceStrip}>
                  <div>
                    <span className={styles.serviceIcon}>
                      <ClipboardList size={17} aria-hidden="true" />
                    </span>
                    <span>
                      <strong>{servicoSelecionado.nome}</strong>
                      <small>{servicoSelecionado.duracao} minutos</small>
                    </span>
                  </div>
                  <strong>{moedaBRL(servicoSelecionado.preco)}</strong>
                </div>
              ) : null}
            </section>

            <section className={styles.stepSection}>
              <div className={styles.stepHeader}>
                <span className={`${styles.stepIndicator} ${horaInicio ? styles.stepComplete : ""}`}>
                  {horaInicio ? <Check size={17} aria-hidden="true" /> : "2"}
                </span>
                <div>
                  <h2>Escolha data e horário</h2>
                  <p>Os horários abaixo refletem a disponibilidade atual.</p>
                </div>
              </div>

              <label className={`${styles.field} ${styles.dateField}`}>
                <span className={styles.fieldLabel}>Data do atendimento</span>
                <span className={styles.controlWrap}>
                  <CalendarDays size={18} aria-hidden="true" />
                  <input
                    className={styles.control}
                    type="date"
                    min={hojeISO()}
                    value={data}
                    onChange={(event) => {
                      setData(event.target.value);
                      setHoraInicio(null);
                    }}
                  />
                </span>
              </label>

              <div className={styles.scheduleHeader}>
                <span>Horários disponíveis</span>
                <div className={styles.legend} aria-label="Legenda dos horários">
                  <span><i className={styles.availableDot} />Disponível</span>
                  <span><i className={styles.unavailableDot} />Indisponível</span>
                </div>
              </div>

              <div className={styles.slots} aria-busy={loadingHorarios}>
                {loadingHorarios ? (
                  Array.from({ length: 10 }).map((_, index) => (
                    <span className={styles.slotSkeleton} key={index} />
                  ))
                ) : lookup.horarios_grade.length ? (
                  lookup.horarios_grade.map((slot) => {
                    const selecionado = horaInicio === slot.hora;
                    return (
                      <button
                        key={slot.hora}
                        type="button"
                        disabled={!slot.disponivel}
                        aria-pressed={selecionado}
                        aria-label={`${slot.hora} - ${slot.disponivel ? "disponível" : "indisponível"}`}
                        title={slot.disponivel ? `Selecionar ${slot.hora}` : "Horário indisponível"}
                        onClick={() => setHoraInicio(slot.hora)}
                        className={`${styles.slot} ${
                          !slot.disponivel ? styles.slotUnavailable : ""
                        } ${selecionado ? styles.slotSelected : ""}`}
                      >
                        <span>{slot.hora}</span>
                        {selecionado ? <Check size={15} aria-hidden="true" /> : null}
                      </button>
                    );
                  })
                ) : (
                  <div className={styles.emptySlots}>
                    <Clock3 size={20} aria-hidden="true" />
                    <span>Não há horários disponíveis nesta data.</span>
                  </div>
                )}
              </div>
            </section>

            <section className={styles.stepSection}>
              <div className={styles.stepHeader}>
                <span
                  className={`${styles.stepIndicator} ${
                    dadosClientePreenchidos ? styles.stepComplete : ""
                  }`}
                >
                  {dadosClientePreenchidos ? <Check size={17} aria-hidden="true" /> : "3"}
                </span>
                <div>
                  <h2>Seus dados</h2>
                  <p>Usaremos esses dados para enviar a confirmação.</p>
                </div>
              </div>

              <div className={styles.customerGrid}>
                <label className={`${styles.field} ${styles.fullField}`}>
                  <span className={styles.fieldLabel}>Nome completo</span>
                  <span className={styles.controlWrap}>
                    <UserRound size={18} aria-hidden="true" />
                    <input
                      className={styles.control}
                      required
                      autoComplete="name"
                      value={nomeCliente}
                      onChange={(event) => setNomeCliente(event.target.value)}
                      placeholder="Ex.: Joao Silva"
                    />
                  </span>
                </label>

                <label className={styles.field}>
                  <span className={styles.fieldLabel}>Telefone (WhatsApp)</span>
                  <span className={styles.controlWrap}>
                    <MessageCircle size={18} aria-hidden="true" />
                    <input
                      className={styles.control}
                      required
                      type="tel"
                      inputMode="tel"
                      autoComplete="tel"
                      value={telefoneCliente}
                      onChange={(event) => setTelefoneCliente(formatarTelefone(event.target.value))}
                      placeholder="(82) 99999-0000"
                    />
                  </span>
                </label>

                <label className={styles.field}>
                  <span className={styles.fieldLabel}>E-mail</span>
                  <span className={styles.controlWrap}>
                    <Mail size={18} aria-hidden="true" />
                    <input
                      className={styles.control}
                      required
                      type="email"
                      autoComplete="email"
                      value={emailCliente}
                      onChange={(event) => setEmailCliente(event.target.value)}
                      placeholder="cliente@email.com"
                    />
                  </span>
                </label>
              </div>
            </section>
          </div>

          <aside className={styles.summaryPanel} aria-label="Resumo do agendamento">
            <div className={styles.summaryHeading}>
              <p>Seu agendamento</p>
              <h2>Revise os detalhes</h2>
            </div>

            <div className={styles.summaryList}>
              <div className={styles.summaryItem}>
                <span><ClipboardList size={17} aria-hidden="true" /></span>
                <div><small>Serviço</small><strong>{servicoSelecionado?.nome ?? "-"}</strong></div>
              </div>
              <div className={styles.summaryItem}>
                <span><UserRound size={17} aria-hidden="true" /></span>
                <div><small>Profissional</small><strong>{barbeiroSelecionado?.nome ?? "-"}</strong></div>
              </div>
              <div className={styles.summaryItem}>
                <span><CalendarDays size={17} aria-hidden="true" /></span>
                <div><small>Data</small><strong>{formatarData(data)}</strong></div>
              </div>
              <div className={styles.summaryItem}>
                <span><Clock3 size={17} aria-hidden="true" /></span>
                <div>
                  <small>Horário</small>
                  <strong className={!horaInicio ? styles.pendingValue : ""}>
                    {horaInicio ?? "Selecione um horário"}
                  </strong>
                </div>
              </div>
            </div>

            <div className={styles.totalRow}>
              <span>{tipoPagamentoAdiantado === "signal" ? "Pagar agora" : "Total"}</span>
              <strong>
                {servicoSelecionado
                  ? moedaBRL(
                      tipoPagamentoAdiantado === "signal"
                        ? valorPagamentoAdiantado
                        : servicoSelecionado.preco
                    )
                  : "-"}
              </strong>
            </div>

            {pagamentoAdiantadoObrigatorio ? (
              <div className={styles.paymentNotice}>
                <ShieldCheck size={19} aria-hidden="true" />
                <p>
                  <strong>
                    {tipoPagamentoAdiantado === "signal"
                      ? "Sinal online obrigatório"
                      : "Pagamento antecipado"}
                  </strong>
                  O horário fica reservado por 5 minutos durante o pagamento.
                </p>
              </div>
            ) : null}

            <div className={styles.feedback} aria-live="polite">
              {erro ? (
                <div className={styles.errorAlert} role="alert">
                  <AlertCircle size={18} aria-hidden="true" />
                  <span>{erro}</span>
                </div>
              ) : null}
              {sucesso ? (
                <div className={styles.successAlert}>
                  <CheckCircle2 size={18} aria-hidden="true" />
                  <span>{sucesso}</span>
                </div>
              ) : null}
            </div>

            <button
              className={styles.submitButton}
              type="submit"
              disabled={submitting || loadingHorarios || !horaInicio}
              aria-busy={submitting}
            >
              {submitting ? (
                <><LoaderCircle className={styles.buttonSpinner} size={19} aria-hidden="true" />Processando</>
              ) : !horaInicio ? (
                <><Clock3 size={19} aria-hidden="true" />Escolha um horário</>
              ) : pagamentoAdiantadoObrigatorio ? (
                <><CreditCard size={19} aria-hidden="true" />Pagar e confirmar</>
              ) : (
                <><CalendarCheck size={19} aria-hidden="true" />Confirmar agendamento</>
              )}
            </button>
          </aside>
=======
    <main className="min-h-screen overflow-x-hidden bg-[#f4f5f2] pb-28 text-zinc-950 lg:pb-12">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-zinc-950 text-white">
              <Scissors className="size-5" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-base font-extrabold text-zinc-950">{lookup.nome}</p>
              <p className="text-xs font-medium text-zinc-500">Agendamento online</p>
            </div>
          </div>
          <div className="hidden items-center gap-2 text-xs font-semibold text-zinc-500 sm:flex">
            <ShieldCheck className="size-4 text-emerald-700" />
            Ambiente seguro
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        <div className="mb-6 flex items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="mb-2 text-xs font-bold uppercase text-emerald-700">Reserve seu horário</p>
            <h1 className="max-w-2xl break-words text-2xl font-extrabold text-zinc-950 sm:text-3xl">
              Escolha o melhor momento para você
            </h1>
            <p className="mt-2 max-w-xl text-sm text-zinc-600">
              Selecione o serviço, o profissional e um horário disponível. Leva menos de um minuto.
            </p>
          </div>
          <p className="hidden text-sm font-semibold text-zinc-500 md:block">
            {horariosDisponiveis} horários disponíveis
          </p>
        </div>

        <form className="grid min-w-0 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]" onSubmit={onSubmit}>
          <section className="min-w-0 overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm">
            <div className="border-b border-zinc-200 px-4 py-5 sm:px-6">
              <StepHeader number="1" title="Escolha seu atendimento" description="Serviço, profissional e data" />

              <div className="mt-5 grid min-w-0 gap-4 sm:grid-cols-2">
                <FieldLabel icon={<Scissors className="size-4" />} label="Serviço">
                  <select
                    className="select min-h-12 w-full min-w-0 bg-white"
                    value={servicoId ?? ""}
                    onChange={(event) => {
                      const valor = Number(event.target.value);
                      setServicoId(Number.isFinite(valor) ? valor : null);
                      setHoraInicio(null);
                    }}
                  >
                    {lookup.servicos.map((servico) => (
                      <option key={servico.id} value={servico.id}>
                        {servico.nome} - {moedaBRL(servico.preco)}
                      </option>
                    ))}
                  </select>
                </FieldLabel>

                <FieldLabel icon={<UsersRound className="size-4" />} label="Profissional">
                  <select
                    className="select min-h-12 w-full min-w-0 bg-white"
                    value={barbeiroId ?? ""}
                    onChange={(event) => {
                      const valor = Number(event.target.value);
                      setBarbeiroId(Number.isFinite(valor) ? valor : null);
                      setHoraInicio(null);
                    }}
                  >
                    {lookup.barbeiros.map((barbeiro) => (
                      <option key={barbeiro.id} value={barbeiro.id}>
                        {barbeiro.nome}
                      </option>
                    ))}
                  </select>
                </FieldLabel>

                <FieldLabel
                  className="sm:col-span-2"
                  icon={<CalendarDays className="size-4" />}
                  label="Data do atendimento"
                >
                  <input
                    className="input min-h-12 bg-white"
                    type="date"
                    min={hojeISO()}
                    value={data}
                    onChange={(event) => {
                      setData(event.target.value);
                      setHoraInicio(null);
                    }}
                  />
                </FieldLabel>
              </div>
            </div>

            <div className="border-b border-zinc-200 px-4 py-5 sm:px-6">
              <div className="flex items-center justify-between gap-3">
                <StepHeader number="2" title="Escolha um horário" description={dataFormatada} />
                <span className="text-xs font-semibold text-emerald-700">{horariosDisponiveis} livres</span>
              </div>

              <div className="mt-5 grid min-w-0 grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5">
                {lookup.horarios_grade.map((slot) => {
                  const selecionado = horaInicio === slot.hora;
                  return (
                    <button
                      key={slot.hora}
                      type="button"
                      disabled={!slot.disponivel}
                      onClick={() => setHoraInicio(slot.hora)}
                      aria-pressed={selecionado}
                      className={[
                        "flex min-h-11 items-center justify-center rounded-lg border px-2 text-sm font-bold transition",
                        slot.disponivel
                          ? "border-zinc-300 bg-white text-zinc-800 hover:border-emerald-600 hover:bg-emerald-50 hover:text-emerald-800"
                          : "cursor-not-allowed border-zinc-200 bg-zinc-100 text-zinc-400 line-through",
                        selecionado
                          ? "border-emerald-700 bg-emerald-700 text-white shadow-sm hover:bg-emerald-700 hover:text-white"
                          : "",
                      ].join(" ")}
                    >
                      {selecionado && <Check className="mr-1 size-4" />}
                      {slot.hora}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="px-4 py-5 sm:px-6">
              <StepHeader number="3" title="Seus dados" description="Usaremos para confirmar o agendamento" />

              <div className="mt-5 grid min-w-0 gap-4 sm:grid-cols-2">
                <FieldLabel className="sm:col-span-2" icon={<UserRound className="size-4" />} label="Nome completo">
                  <input
                    className="input min-h-12 bg-white"
                    autoComplete="name"
                    required
                    value={nomeCliente}
                    onChange={(event) => setNomeCliente(event.target.value)}
                    placeholder="Como devemos chamar você?"
                  />
                </FieldLabel>
                <FieldLabel icon={<Smartphone className="size-4" />} label="WhatsApp">
                  <input
                    className="input min-h-12 bg-white"
                    autoComplete="tel"
                    inputMode="tel"
                    required
                    value={telefoneCliente}
                    onChange={(event) => setTelefoneCliente(event.target.value)}
                    placeholder="(82) 99999-0000"
                  />
                </FieldLabel>
                <FieldLabel icon={<Mail className="size-4" />} label="Email">
                  <input
                    className="input min-h-12 bg-white"
                    autoComplete="email"
                    required
                    type="email"
                    value={emailCliente}
                    onChange={(event) => setEmailCliente(event.target.value)}
                    placeholder="voce@email.com"
                  />
                </FieldLabel>
              </div>
            </div>

            <div className="px-4 pb-5 sm:px-6 lg:hidden">
              <Feedback error={erro} success={sucesso} />
            </div>
          </section>

          <aside className="hidden lg:sticky lg:top-6 lg:block">
            <div className="rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
              <div className="mb-5 flex items-center justify-between">
                <h2 className="text-base font-extrabold text-zinc-950">Resumo</h2>
                <Clock3 className="size-5 text-zinc-400" />
              </div>

              <div className="space-y-4 text-sm">
                <div>
                  <p className="text-xs font-semibold text-zinc-500">Serviço</p>
                  <p className="mt-1 font-bold text-zinc-900">{servicoSelecionado?.nome ?? "-"}</p>
                  <p className="mt-0.5 text-xs text-zinc-500">
                    {servicoSelecionado ? `${servicoSelecionado.duracao} minutos` : "-"}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-3 border-y border-zinc-200 py-4">
                  <div>
                    <p className="text-xs font-semibold text-zinc-500">Profissional</p>
                    <p className="mt-1 font-bold text-zinc-900">{barbeiroSelecionado?.nome ?? "-"}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-zinc-500">Horário</p>
                    <p className="mt-1 font-bold capitalize text-zinc-900">
                      {horaInicio ? `${dataFormatada}, ${horaInicio}` : "Escolha um horário"}
                    </p>
                  </div>
                </div>
                <div className="flex items-end justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold text-zinc-500">
                      {pagamentoAdiantadoObrigatorio && tipoPagamentoAdiantado === "signal" ? "Sinal online" : "Total"}
                    </p>
                    <p className="mt-1 text-2xl font-extrabold text-zinc-950">
                      {servicoSelecionado ? moedaBRL(valorParaConfirmar) : "-"}
                    </p>
                  </div>
                  {pagamentoAdiantadoObrigatorio && <CreditCard className="size-5 text-emerald-700" />}
                </div>
              </div>

              {pagamentoAdiantadoObrigatorio && (
                <div className="mt-5 border-l-2 border-amber-500 bg-amber-50 px-3 py-2.5 text-xs font-medium text-amber-950">
                  O horário fica reservado enquanto você conclui o pagamento.
                </div>
              )}

              <div className="mt-4">
                <Feedback error={erro} success={sucesso} />
              </div>

              <SubmitButton
                disabled={submitting || !podeConfirmar}
                loading={submitting}
                paymentRequired={pagamentoAdiantadoObrigatorio}
              />
              <p className="mt-3 flex items-center justify-center gap-1.5 text-center text-[11px] font-medium text-zinc-500">
                <ShieldCheck className="size-3.5" />
                Seus dados estão protegidos
              </p>
            </div>
          </aside>

          <div className="fixed inset-x-0 bottom-0 z-40 overflow-hidden border-t border-zinc-200 bg-white/95 px-4 py-3 shadow-[0_-8px_24px_rgba(0,0,0,0.08)] backdrop-blur lg:hidden">
            <div className="mx-auto flex min-w-0 max-w-6xl items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold text-zinc-500">
                  {horaInicio
                    ? `${servicoSelecionado?.nome ?? "Serviço"} - ${dataFormatada}, ${horaInicio}`
                    : "Escolha um horário para continuar"}
                </p>
                <p className="text-lg font-extrabold text-zinc-950">
                  {servicoSelecionado ? moedaBRL(valorParaConfirmar) : "-"}
                </p>
              </div>
              <SubmitButton
                compact
                disabled={submitting || !podeConfirmar}
                loading={submitting}
                paymentRequired={pagamentoAdiantadoObrigatorio}
              />
            </div>
          </div>
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
        </form>
      </div>

      {showPaymentNotice && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4"
          role="presentation"
          onMouseDown={(event) => {
            if (event.currentTarget === event.target && !submitting) {
              setShowPaymentNotice(false);
            }
          }}
        >
          <section
            aria-describedby="payment-notice-description"
            aria-labelledby="payment-notice-title"
            aria-modal="true"
            className="w-full border border-zinc-200 bg-white p-5 shadow-2xl sm:max-w-lg sm:rounded-lg sm:p-6"
            role="alertdialog"
          >
            <div className="flex items-start gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-800">
                <CircleAlert className="size-5" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-bold uppercase text-amber-700">Antes de continuar</p>
                <h2 id="payment-notice-title" className="mt-1 text-xl font-extrabold text-zinc-950">
                  Como conferir seu pagamento
                </h2>
              </div>
            </div>

            <p id="payment-notice-description" className="mt-4 text-sm leading-6 text-zinc-600">
              Você será direcionado ao Mercado Pago. Assim que concluir o pagamento, toque no botão abaixo da tela do
              Pix para retornar e conferir se o agendamento foi aprovado.
            </p>

            <div className="mt-4 border-l-2 border-emerald-600 bg-emerald-50 px-4 py-3">
              <p className="text-xs font-semibold text-emerald-800">No Mercado Pago, procure por:</p>
              <p className="mt-1 flex items-center gap-2 text-sm font-extrabold text-emerald-950">
                <ArrowLeft className="size-4 shrink-0" />
                Voltar para {lookup.nome}
              </p>
            </div>

            <p className="mt-4 text-xs leading-5 text-zinc-500">
              Ao voltar, o sistema verificará automaticamente o pagamento e mostrará a confirmação do seu horário.
            </p>

            <div className="mt-6 grid gap-2 sm:grid-cols-[1fr_auto]">
              <button
                className="order-2 min-h-12 rounded-lg border border-zinc-300 px-4 text-sm font-bold text-zinc-700 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50 sm:order-1"
                type="button"
                disabled={submitting}
                onClick={() => setShowPaymentNotice(false)}
              >
                Voltar
              </button>
              <button
                className="order-1 flex min-h-12 items-center justify-center gap-2 rounded-lg bg-emerald-700 px-5 text-sm font-bold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-zinc-300 sm:order-2"
                type="button"
                autoFocus
                disabled={submitting}
                onClick={() => {
                  setShowPaymentNotice(false);
                  void concluirAgendamento();
                }}
              >
                {submitting ? <LoaderCircle className="size-4 animate-spin" /> : <ExternalLink className="size-4" />}
                {submitting ? "Abrindo pagamento..." : "Entendi, ir para pagamento"}
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function StepHeader({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-zinc-950 text-xs font-bold text-white">
        {number}
      </span>
      <div className="min-w-0">
        <h2 className="break-words text-base font-extrabold text-zinc-950">{title}</h2>
        <p className="text-xs capitalize text-zinc-500">{description}</p>
      </div>
    </div>
  );
}

function FieldLabel({
  children,
  className = "",
  icon,
  label,
}: {
  children: React.ReactNode;
  className?: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <label className={`block min-w-0 ${className}`}>
      <span className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-zinc-800">
        <span className="text-zinc-500">{icon}</span>
        {label}
      </span>
      {children}
    </label>
  );
}

function Feedback({ error, success }: { error: string | null; success: string | null }) {
  if (error) {
    return <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{error}</p>;
  }
  if (success) {
    return (
      <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
        {success}
      </p>
    );
  }
  return null;
}

function SubmitButton({
  compact = false,
  disabled,
  loading,
  paymentRequired,
}: {
  compact?: boolean;
  disabled: boolean;
  loading: boolean;
  paymentRequired: boolean;
}) {
  return (
    <button
      className={[
        "flex min-h-12 items-center justify-center gap-2 rounded-lg bg-emerald-700 text-sm font-bold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-zinc-200 disabled:text-zinc-500",
        compact ? "shrink-0 px-4" : "mt-5 w-full px-4",
      ].join(" ")}
      type="submit"
      disabled={disabled}
    >
      {loading && <LoaderCircle className="size-4 animate-spin" />}
      {loading ? "Aguarde" : compact ? (paymentRequired ? "Pagar" : "Confirmar") : paymentRequired ? "Ir para pagamento" : "Confirmar agendamento"}
      {!loading && <ArrowRight className="size-4" />}
    </button>
  );
}
