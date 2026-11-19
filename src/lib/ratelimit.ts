import type { Db } from "./db";

/**
 * Límite de intentos persistente (tabla `rate_limits`). En Cloudflare Workers una variable en memoria no sirve:
 * cada petición puede caer en una instancia distinta. Ventana fija por clave.
 */

/** Cuenta una acción para `key` y devuelve cuántas van en la ventana actual (incluida esta). */
export async function rateHit(db: Db, key: string, windowSec: number): Promise<number> {
  const [r] = await db.query<{ count: number }>(
    `INSERT INTO rate_limits (key, window_start, count) VALUES ($1, now(), 1)
     ON CONFLICT (key) DO UPDATE SET
       count = CASE WHEN rate_limits.window_start < now() - make_interval(secs => $2::int) THEN 1 ELSE rate_limits.count + 1 END,
       window_start = CASE WHEN rate_limits.window_start < now() - make_interval(secs => $2::int) THEN now() ELSE rate_limits.window_start END
     RETURNING count`,
    [key, windowSec],
  );
  if (Math.random() < 0.02) await db.query("DELETE FROM rate_limits WHERE window_start < now() - interval '1 day'").catch(() => undefined);
  return r.count;
}

/** Cuántas acciones lleva `key` en la ventana actual, sin contar una nueva. */
export async function rateCount(db: Db, key: string, windowSec: number): Promise<number> {
  const [r] = await db.query<{ count: number }>(
    "SELECT count FROM rate_limits WHERE key = $1 AND window_start >= now() - make_interval(secs => $2::int)",
    [key, windowSec],
  );
  return r?.count ?? 0;
}

export async function rateReset(db: Db, key: string): Promise<void> {
  await db.query("DELETE FROM rate_limits WHERE key = $1", [key]);
}
