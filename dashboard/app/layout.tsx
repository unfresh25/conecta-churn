import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Conecta+ · Retención",
  description: "A quién llamar en enero de 2026, cuánto se espera ganar y por qué cada cliente está en riesgo.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
