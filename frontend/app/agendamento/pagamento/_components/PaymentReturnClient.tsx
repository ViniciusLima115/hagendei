"use client";

import { CheckCircle2, Clock3, XCircle } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getPublicPaymentStatus, PublicPaymentStatusResponse } from "@/services/api";

type Variant = "sucesso" | "pendente" | "falha";

const TITLES: Record<Variant, string> = {
  sucesso: "Pagamento aprovado",
  pendente: "Pagamento em processamento",
  falha: "Pagamento nao concluido",
};

const DESCRIPTIONS: Record<Variant, string> = {
  sucesso: "Pagamento confirmado. Seu agendamento esta reservado.",
  pendente: "Estamos aguardando a confirmacao do Mercado Pago. Esta pagina sera atualizada automaticamente.",
  falha: "Nao houve confirmacao do pagamento. O agendamento nao sera confirmado como pago sem aprovacao oficial do webhook.",
};

const PAYMENT_STATUS_LABELS: Record<PublicPaymentStatusResponse["pagamento_status"], string> = {
  pending: "Aguardando pagamento",
  approved: "Aprovado",
  rejected: "Recusado",
  cancelled: "Cancelado",
  refunded: "Estornado",
  expired: "Expirado",
};

const BOOKING_STATUS_LABELS: Record<PublicPaymentStatusResponse["agendamento_status"], string> = {
  pending_payment: "Aguardando pagamento",
  pendente: "Pendente",
  confirmado: "Confirmado",
  cancelado: "Cancelado",
  failed: "Falhou",
  expired: "Expirado",
};

const FINAL_PAYMENT_STATUSES = new Set<PublicPaymentStatusResponse["pagamento_status"]>([
  "approved",
  "rejected",
  "cancelled",
  "refunded",
  "expired",
]);

function statusVariant(
  status: PublicPaymentStatusResponse | null,
  fallback: Variant,
): Variant {
  if (!status) return fallback;
  if (status.pagamento_status === "approved" || status.agendamento_status === "confirmado") {
    return "sucesso";
  }
  if (
    ["rejected", "cancelled", "refunded", "expired"].includes(status.pagamento_status)
    || ["cancelado", "failed", "expired"].includes(status.agendamento_status)
  ) {
    return "falha";
  }
  return "pendente";
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

function PaymentReturnInner({ variant }: { variant: Variant }) {
  const searchParams = useSearchParams();
  const externalReference = searchParams.get("external_reference") || "";

  const [status, setStatus] = useState<PublicPaymentStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const paymentFinalRef = useRef(false);
  const returnSlug = status?.slug || searchParams.get("slug") || "";
  const bookingHref = returnSlug ? `/${encodeURIComponent(returnSlug)}` : null;

  useEffect(() => {
    let mounted = true;
    paymentFinalRef.current = false;

    async function loadStatus() {
      if (!externalReference) {
        if (!mounted) return;
        setLoading(false);
        setError("Referencia de pagamento nao encontrada no retorno.");
        return;
      }

      try {
        const result = await getPublicPaymentStatus(externalReference);
        if (!mounted) return;
        setStatus(result);
        paymentFinalRef.current = FINAL_PAYMENT_STATUSES.has(result.pagamento_status);
        setError(null);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Falha ao consultar status do pagamento.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadStatus();

    const intervalId = window.setInterval(() => {
      if (!paymentFinalRef.current) {
        void loadStatus();
      }
    }, 3000);
    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, [externalReference]);

  const visualVariant = statusVariant(status, variant);
  const StatusIcon = visualVariant === "sucesso"
    ? CheckCircle2
    : visualVariant === "falha"
      ? XCircle
      : Clock3;
  const iconClasses = visualVariant === "sucesso"
    ? "text-emerald-600"
    : visualVariant === "falha"
      ? "text-red-600"
      : "text-amber-600";

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-10">
      <div className="mx-auto max-w-xl rounded-2xl bg-white p-6 shadow">
        <StatusIcon aria-hidden="true" className={`mb-4 size-10 ${iconClasses}`} />
        <h1 className="text-2xl font-bold text-slate-900">{TITLES[visualVariant]}</h1>
        <p className="mt-2 text-sm text-slate-600">{DESCRIPTIONS[visualVariant]}</p>

        {!externalReference && (
          <p className="mt-4 rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900">
            Sem referencia de pagamento no retorno.
          </p>
        )}

        {loading && <p className="mt-4 text-sm text-slate-600">Consultando status...</p>}

        {error && (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}

        {status && (
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <p><strong>Referencia:</strong> {status.external_reference}</p>
            <p><strong>Agendamento:</strong> #{status.agendamento_id}</p>
            <p><strong>Status do pagamento:</strong> {PAYMENT_STATUS_LABELS[status.pagamento_status]}</p>
            <p><strong>Status do agendamento:</strong> {BOOKING_STATUS_LABELS[status.agendamento_status]}</p>
            <p><strong>Valor:</strong> {formatCurrency(status.amount)}</p>
          </div>
        )}

        {bookingHref && (
          <div className="mt-6 flex gap-3">
            <Link href={bookingHref} className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white">
              Voltar ao agendamento
            </Link>
          </div>
        )}
      </div>
    </main>
  );
}

export function PaymentReturnClient({ variant }: { variant: Variant }) {
  return (
    <Suspense fallback={<main className="min-h-screen bg-slate-100" />}>
      <PaymentReturnInner variant={variant} />
    </Suspense>
  );
}
