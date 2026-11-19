import type { Db } from "./db";

/** Estado de seguridad del panel guardado en la tabla `settings` (claves internas, no editables desde Ajustes). */

/** Época de sesión: cambiarla revoca todas las sesiones ya emitidas. */
export async function getEpoch(db: Db): Promise<number> {
  const [r] = await db.query<{ value: string }>("SELECT value FROM settings WHERE key = 'admin_epoch'");
  return Number.parseInt(r?.value ?? "0", 10) || 0;
}

export async function bumpEpoch(db: Db): Promise<void> {
  await db.query(
    `INSERT INTO settings (key, value) VALUES ('admin_epoch', '1')
     ON CONFLICT (key) DO UPDATE SET value = (settings.value::bigint + 1)::text`,
  );
}

/** Marca un contador TOTP como usado. Devuelve false si ese código (o uno posterior) ya se usó: evita reutilizarlo. */
export async function claimTotp(db: Db, counter: number): Promise<boolean> {
  const rows = await db.query(
    `INSERT INTO settings (key, value) VALUES ('totp_last', $1::text)
     ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
     WHERE settings.value::bigint < EXCLUDED.value::bigint
     RETURNING value`,
    [counter],
  );
  return rows.length > 0;
}
