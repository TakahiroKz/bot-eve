import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { siteUrl } from "@/lib/env";

const oswald = localFont({
  src: [
    { path: "./fonts/oswald-latin-400-normal.woff2", weight: "400" },
    { path: "./fonts/oswald-latin-500-normal.woff2", weight: "500" },
    { path: "./fonts/oswald-latin-600-normal.woff2", weight: "600" },
  ],
  variable: "--font-oswald",
  display: "swap",
});
const inter = localFont({
  src: [
    { path: "./fonts/inter-latin-400-normal.woff2", weight: "400" },
    { path: "./fonts/inter-latin-500-normal.woff2", weight: "500" },
  ],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl()),
  title: { default: "Nerova · Chaquetas de cuero", template: "%s · Nerova" },
  description: "Nerova: chaquetas de cuero diseñadas para quien no necesita explicarse. Envíos a toda Colombia.",
  openGraph: { type: "website", locale: "es_CO", siteName: "Nerova" },
};

export const viewport: Viewport = { themeColor: "#0b0b0c" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es-CO" className={`${oswald.variable} ${inter.variable}`}>
      <body>{children}</body>
    </html>
  );
}
