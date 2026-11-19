// Crea el esquema y los datos iniciales en la base indicada por DATABASE_URL (necesario con Cloudflare/Hyperdrive,
// donde la aplicación no ejecuta DDL en cada petición).   DATABASE_URL=postgres://... npm run db:migrate
import pg from "pg";
import { SCHEMA_SQL } from "../src/lib/schema.ts";
import { seedIfEmpty } from "../src/lib/seed.ts";

if (!process.env.DATABASE_URL) {
  console.error("Falta DATABASE_URL");
  process.exit(1);
}
const c = new pg.Client({ connectionString: process.env.DATABASE_URL });
await c.connect();
await c.query(SCHEMA_SQL);
await seedIfEmpty({
  query: async (sql, params = []) => (await c.query(sql, params)).rows,
  tx: async () => {
    throw new Error("no usado");
  },
});
await c.end();
console.log("Base lista.");
