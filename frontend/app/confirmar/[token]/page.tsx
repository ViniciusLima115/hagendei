import BookingTokenActionCard from "@/app/components/BookingTokenActionCard";

export default function ConfirmarAgendamentoPage({
  params,
}: {
  params: { token: string };
}) {
  return <BookingTokenActionCard token={params.token} mode="confirmar" />;
}
