"use client";

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
  lookupPublicEstabelecimento,
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
  return new Intl.DateTimeFormat("pt-BR", {
    weekday: "short",
    day: "2-digit",
    month: "short",
  }).format(new Date(ano, mes - 1, dia));
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
        const base = await lookupPublicEstabelecimento({ slug });
        if (!ativo) return;
        setLookup(base);

        const primeiroBarbeiro = base.barbeiros[0]?.id ?? null;
        const primeiroServico = base.servicos[0]?.id ?? null;
        setBarbeiroId(primeiroBarbeiro);
        setServicoId(primeiroServico);
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
        const atualizado = await lookupPublicEstabelecimento({
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
            (slot) => slot.hora === horaAtual && slot.disponivel
          );
          return aindaDisponivel ? horaAtual : null;
        });
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Falha ao carregar horários.");
      } finally {
        if (ativo) setLoadingHorarios(false);
      }
    }

    carregarDisponibilidade();
    return () => {
      ativo = false;
    };
  }, [slug, barbeiroId, servicoId, data]);

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
  const dadosClientePreenchidos = Boolean(
    nomeCliente.trim() && normalizarTelefone(telefoneCliente) && emailCliente.trim()
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!slug || !barbeiroId || !servicoId || !horaInicio) {
      setErro("Preencha todos os campos e selecione um horário disponível.");
      return;
    }
    if (!nomeCliente.trim() || !normalizarTelefone(telefoneCliente) || !emailCliente.trim()) {
      setErro("Preencha nome, telefone e e-mail.");
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
        setSucesso("Seu horário foi reservado por 5 minutos. Redirecionando para o checkout...");
        const pagamento = await startPublicBookingPayment(payload);
        window.location.href = pagamento.checkout_url;
        return;
      }

      await createPublicBooking(payload);
      setSucesso("Agendamento criado. Enviamos a confirmação por e-mail.");
      setHoraInicio(null);

      const atualizado = await lookupPublicEstabelecimento({
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

  if (loading) {
    return (
      <main className={styles.page}>
        <div className={styles.statePanel} role="status">
          <LoaderCircle className={styles.stateSpinner} size={24} aria-hidden="true" />
          <div>
            <strong>Preparando seu agendamento</strong>
            <p>Buscando profissionais, serviços e horários disponíveis.</p>
          </div>
        </div>
      </main>
    );
  }

  if (!lookup) {
    return (
      <main className={styles.page}>
        <div className={styles.statePanel} role="alert">
          <AlertCircle size={24} aria-hidden="true" />
          <div>
            <strong>Página indisponível</strong>
            <p>{erro ?? "Estabelecimento não encontrado para este link."}</p>
          </div>
        </div>
      </main>
    );
  }

  return (
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
        </form>
      </div>
    </main>
  );
}
