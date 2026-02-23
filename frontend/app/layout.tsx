import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Painel da Barbearia",
  description: "Agenda e gestão de agendamentos da barbearia",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
