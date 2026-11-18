import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { verifySession } from "./auth";
import { adminPath } from "./env";

export const ADMIN_COOKIE = "adm";
export const ADMIN_TTL_MS = 8 * 60 * 60 * 1000;

/** URL pública del panel (la ruta secreta), p. ej. `adminUrl("/pedidos")`. */
export const adminUrl = (sub = "") => adminPath() + sub;

export async function isAdmin(): Promise<boolean> {
  return verifySession((await cookies()).get(ADMIN_COOKIE)?.value);
}

/** Úsalo al inicio de CADA página y acción del panel: el layout por sí solo no protege las acciones. */
export async function requireAdmin(): Promise<void> {
  if (!(await isAdmin())) redirect(adminUrl("/login"));
}
