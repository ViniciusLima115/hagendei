import BookingTokenActionCard from "@/app/components/BookingTokenActionCard";

export default function CancelarAgendamentoPage({
  params,
}: {
  params: { token: string };
}) {
  return <BookingTokenActionCard token={params.token} mode="cancelar" />;
}
