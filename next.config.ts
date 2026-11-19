import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

/**
 * Política de contenido. Next.js inyecta scripts en línea para hidratar la página, por eso `script-src` admite
 * 'unsafe-inline' (en desarrollo también 'unsafe-eval', que usa el recargador en caliente). El resto está cerrado:
 * nada se puede incrustar en otros sitios (frame-ancestors), ni cargar plugins, ni enviar formularios a otro origen.
 * Si más adelante la pasarela de pagos necesita un script o un iframe propios, se agrega su dominio aquí.
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isProd ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: https:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(isProd ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const config: NextConfig = {
  poweredByHeader: false,
  serverExternalPackages: ["@electric-sql/pglite", "pg"],
  images: { remotePatterns: [] },
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders },
      // Páginas con datos personales o de sesión: nunca se guardan en cachés compartidas.
      ...["/pedido/:path*", "/checkout", "/carrito", "/pago/:path*"].map((source) => ({
        source,
        headers: [{ key: "Cache-Control", value: "private, no-store" }],
      })),
    ];
  },
};

export default config;
