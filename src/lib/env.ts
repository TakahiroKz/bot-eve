/** Lectura centralizada de variables de entorno. */
export function adminPath(): string {
  const raw = (process.env.ADMIN_PATH ?? "/gestion-privada").trim();
  const p = "/" + raw.replace(/^\/+|\/+$/g, "");
  if (p === "/" || /[^a-zA-Z0-9\-_/]/.test(p)) throw new Error("ADMIN_PATH inválido");
  return p;
}

export function sessionSecret(): string {
  const s = process.env.SESSION_SECRET ?? "";
  if (s.length < 32) {
    if (process.env.NODE_ENV === "production") throw new Error("SESSION_SECRET debe tener al menos 32 caracteres");
    return "solo-desarrollo-solo-desarrollo-solo-desarrollo";
  }
  return s;
}

export function siteUrl(): string {
  return (process.env.SITE_URL ?? "http://localhost:3000").replace(/\/+$/, "");
}
