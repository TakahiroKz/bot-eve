import { mkdirSync } from "node:fs";
import { PGlite } from "@electric-sql/pglite";
import { Pool } from "pg";
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

/** Crea una base en memoria (pruebas). */
export async function memoryDb(): Promise<Db> {
  const pg = new PGlite();
  await pg.exec(SCHEMA_SQL);
  return fromPglite(pg);
}

export function getDb(): Promise<Db> {
  g.__db ??= (async () => {
    if (process.env.DATABASE_URL) {
      const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 5 });
      await pool.query(SCHEMA_SQL);
      const db = fromPool(pool);
      await seedIfEmpty(db);
      return db;
    }
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
