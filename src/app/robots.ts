import type { MetadataRoute } from "next";
import { siteUrl } from "@/lib/env";

// IMPORTANTE: no se menciona la ruta del panel aquí (robots.txt es público y la delataría).
// El panel se protege con autenticación y se excluye de buscadores con `X-Robots-Tag: noindex`.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/carrito", "/checkout", "/pedido/", "/pago/", "/api/"] },
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
