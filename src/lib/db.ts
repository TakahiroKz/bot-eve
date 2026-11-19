import type { PGlite } from "@electric-sql/pglite";
import type { Pool } from "pg";
import { SCHEMA_SQL } from "./schema";
import { seedIfEmpty } from "./seed";

export type Row = Record<string, unknown>;

export interface Db {
  query<T = Row>(sql: string, params?: unknown[]): Promise<T[]>;
  /** Ejecuta `fn` en una transacción (BEGIN/COMMIT, ROLLBACK si lanza). */
  tx<T>(fn: (q: Db["query"]) => Promise<T>): Promise<T>;
}

function fromPglite(pg: PGlite): Db {
  return {
    async query<T>(sql: string, params: unknown[] = []) {
      return (await pg.query<T>(sql, params)).rows;
    },
    tx: (fn) => pg.transaction((t) => fn(async <T>(sql: string, p: unknown[] = []) => (await t.query<T>(sql, p)).rows)),
  };
}

function fromPool(pool: Pool): Db {
  return {
    async query<T>(sql: string, params: unknown[] = []) {
      return (await pool.query(sql, params)).rows as T[];
    },
    async tx(fn) {
      const c = await pool.connect();
      try {
        await c.query("BEGIN");
        const out = await fn(async <T>(sql: string, p: unknown[] = []) => (await c.query(sql, p)).rows as T[]);
        await c.query("COMMIT");
        return out;
      } catch (e) {
        await c.query("ROLLBACK");
        throw e;
      } finally {
        c.release();
      }
    },
  };
}

const g = globalThis as unknown as { __db?: Promise<Db> };

/** En Cloudflare Workers no se puede reutilizar una conexión entre peticiones: cada consulta usa un cliente nuevo
 *  (Hyperdrive mantiene el pool real por debajo). */
async function cloudflareDb(): Promise<Db | null> {
  let url: string | undefined;
  try {
    const { getCloudflareContext } = await import("@opennextjs/cloudflare");
    url = (getCloudflareContext().env as { HYPERDRIVE?: { connectionString: string } }).HYPERDRIVE?.connectionString;
  } catch {
    return null; // no estamos en Cloudflare
  }
  if (!url) return null;
  const { Client } = await import("pg");
  const open = async () => {
    const c = new Client({ connectionString: url });
    await c.connect();
    return c;
  };
  return {
    async query<T>(sql: string, params: unknown[] = []) {
      const c = await open();
      try {
        return (await c.query(sql, params)).rows as T[];
      } finally {
        await c.end();
      }
    },
    async tx(fn) {
      const c = await open();
      try {
        await c.query("BEGIN");
        const out = await fn(async <T>(sql: string, p: unknown[] = []) => (await c.query(sql, p)).rows as T[]);
        await c.query("COMMIT");
        return out;
      } catch (e) {
        await c.query("ROLLBACK").catch(() => undefined);
        throw e;
      } finally {
        await c.end();
      }
    },
  };
}

/** Crea una base en memoria (pruebas). */
export async function memoryDb(): Promise<Db> {
  const { PGlite } = await import("@electric-sql/pglite");
  const pg = new PGlite();
  await pg.exec(SCHEMA_SQL);
  return fromPglite(pg);
}

export async function getDb(): Promise<Db> {
  const cf = await cloudflareDb(); // el esquema y los datos iniciales se cargan con `npm run db:migrate`, no en cada petición
  if (cf) return cf;
  return nodeDb();
}

function nodeDb(): Promise<Db> {
  g.__db ??= (async () => {
    if (process.env.DATABASE_URL) {
      const { Pool } = await import("pg");
      const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 5 });
      await pool.query(SCHEMA_SQL);
      const db = fromPool(pool);
      await seedIfEmpty(db);
      return db;
    }
    const { mkdirSync } = await import("node:fs");
    const { PGlite } = await import("@electric-sql/pglite");
    mkdirSync("./.data", { recursive: true });
    const pg = new PGlite("./.data/pg");
    await pg.exec(SCHEMA_SQL);
    const db = fromPglite(pg);
    await seedIfEmpty(db);
    return db;
  })();
  g.__db.catch(() => {
    g.__db = undefined; // si falla el arranque, el próximo intento vuelve a probar
  });
  return g.__db;
}
