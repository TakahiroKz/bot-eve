import type { Metadata, Viewport } from "next";
import "./globals.css";
import { siteUrl } from "@/lib/env";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: { default: "Chaquetas de cuero", template: "%s · Chaquetas de cuero" },
  description: "Chaquetas de cuero para quien no necesita explicarse. Envíos a toda Colombia.",
  openGraph: { type: "website", locale: "es_CO" },
};

export const viewport: Viewport = { themeColor: "#0b0b0c" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-CO">
      <body>{children}</body>
    </html>
  );
}
