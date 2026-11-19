import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { bumpEpoch, claimTotp, getEpoch } from "../src/lib/admin-state";
import {
  hashPassword, signSession, totpCode, totpMatch, verifyPassword, verifySession, verifyTotp,
} from "../src/lib/auth";
import { memoryDb, type Db } from "../src/lib/db";
import { rateCount, rateHit, rateReset } from "../src/lib/ratelimit";

const SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"; // "12345678901234567890" en base32 (vector RFC 6238)

afterEach(() => {
  delete process.env.ADMIN_PASSWORD_HASH;
  delete process.env.ADMIN_PASSWORD;
});

describe("sesión firmada", () => {
  it("acepta un token válido y rechaza expirado, alterado o vacío", () => {
    const t = signSession(60_000, 1_000);
    expect(verifySession(t, 2_000)).toBe(true);
    expect(verifySession(t, 70_000)).toBe(false);
    const [p, s] = t.split(".");
    expect(verifySession(`${p}x.${s}`, 2_000)).toBe(false);
    expect(verifySession(`${p}.${s.slice(0, -2)}AA`, 2_000)).toBe(false);
    expect(verifySession(undefined)).toBe(false);
    expect(verifySession("basura")).toBe(false);
  });
});

describe("contraseña", () => {
  it("verifica el hash scrypt; sin configuración nadie entra", async () => {
    expect(await verifyPassword("lo-que-sea")).toBe(false);
    process.env.ADMIN_PASSWORD_HASH = await hashPassword("clave-larga-123");
    expect(await verifyPassword("clave-larga-123")).toBe(true);
    expect(await verifyPassword("otra")).toBe(false);
  });
  it("la contraseña en claro solo sirve fuera de producción", async () => {
    process.env.ADMIN_PASSWORD = "dev";
    expect(await verifyPassword("dev")).toBe(true);
  });
});

describe("TOTP", () => {
  it("coincide con los vectores de la RFC 6238 (SHA-1)", () => {
    expect(totpCode(SECRET, 59_000)).toBe("287082");
    expect(totpCode(SECRET, 1111111109_000)).toBe("081804");
  });
  it("tolera ±30 s y rechaza lo demás", () => {
    expect(verifyTotp("287082", SECRET, 59_000)).toBe(true);
    expect(verifyTotp("287082", SECRET, 59_000 + 30_000)).toBe(true);
    expect(verifyTotp("287082", SECRET, 59_000 + 120_000)).toBe(false);
    expect(verifyTotp("12345", SECRET, 59_000)).toBe(false);
    expect(verifyTotp("abcdef", SECRET, 59_000)).toBe(false);
  });
});

describe("sesión revocable (época)", () => {
  it("un token de otra época no vale, y el de la época actual sí", () => {
    const t = signSession(60_000, 1_000, 3);
    expect(verifySession(t, 2_000, 3)).toBe(true);
    expect(verifySession(t, 2_000, 4)).toBe(false);
    expect(verifySession(signSession(60_000, 1_000), 2_000, 0)).toBe(true); // tokens sin época cuentan como 0
  });
});

describe("estado del panel en base de datos", () => {
  let db: Db;
  beforeEach(async () => {
    db = await memoryDb();
  });

  it("incrementa la época al cerrar sesión", async () => {
    expect(await getEpoch(db)).toBe(0);
    await bumpEpoch(db);
    await bumpEpoch(db);
    expect(await getEpoch(db)).toBe(2);
  });

  it("un código TOTP no se puede reutilizar", async () => {
    const counter = totpMatch(totpCode(SECRET, 59_000), SECRET, 59_000);
    expect(counter).not.toBeNull();
    expect(await claimTotp(db, counter!)).toBe(true);
    expect(await claimTotp(db, counter!)).toBe(false); // mismo código otra vez
    expect(await claimTotp(db, counter! - 1)).toBe(false); // uno anterior
    expect(await claimTotp(db, counter! + 1)).toBe(true); // uno posterior sí
  });

  it("limita acciones por ventana y se puede reiniciar", async () => {
    for (let i = 1; i <= 5; i++) expect(await rateHit(db, "login:ip:1.2.3.4", 900)).toBe(i);
    expect(await rateCount(db, "login:ip:1.2.3.4", 900)).toBe(5);
    expect(await rateCount(db, "login:ip:9.9.9.9", 900)).toBe(0); // otra clave no se ve afectada
    await rateReset(db, "login:ip:1.2.3.4");
    expect(await rateCount(db, "login:ip:1.2.3.4", 900)).toBe(0);
  });

  it("la ventana vencida empieza de cero", async () => {
    await rateHit(db, "k", 900);
    await rateHit(db, "k", 900);
    await db.query("UPDATE rate_limits SET window_start = now() - interval '1 hour' WHERE key = 'k'");
    expect(await rateCount(db, "k", 900)).toBe(0);
    expect(await rateHit(db, "k", 900)).toBe(1);
  });
});
