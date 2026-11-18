import { afterEach, describe, expect, it } from "vitest";
import {
  hashPassword, loginBlocked, loginFailed, loginOk, resetAttempts, signSession, totpCode, verifyPassword, verifySession, verifyTotp,
} from "../src/lib/auth";

afterEach(() => {
  delete process.env.ADMIN_PASSWORD_HASH;
  delete process.env.ADMIN_PASSWORD;
  resetAttempts();
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
  const SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"; // "12345678901234567890" en base32 (vector RFC 6238)
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

describe("límite de intentos", () => {
  it("bloquea tras 5 fallos y se levanta con éxito o con el tiempo", () => {
    for (let i = 0; i < 5; i++) loginFailed("ip", 1_000);
    expect(loginBlocked("ip", 2_000)).toBe(true);
    expect(loginBlocked("ip", 1_000 + 16 * 60 * 1000)).toBe(false);
    loginOk("ip");
    expect(loginBlocked("ip", 2_000)).toBe(false);
  });
});
