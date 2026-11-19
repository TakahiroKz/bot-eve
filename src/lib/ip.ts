import { headers } from "next/headers";

/**
 * IP del cliente. Detrás de Cloudflare es `cf-connecting-ip` (lo fija Cloudflare y el cliente no puede falsificarlo).
 * No se usa `x-forwarded-for`: el cliente puede enviarlo con el valor que quiera.
 */
export async function clientIp(): Promise<string> {
  const h = await headers();
  return (h.get("cf-connecting-ip") ?? h.get("x-real-ip") ?? "local").trim().slice(0, 64);
}
