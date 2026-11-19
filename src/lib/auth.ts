import { createHmac, randomBytes, scrypt, timingSafeEqual } from "node:crypto";
import { sessionSecret } from "./env";

const b64u = (b: Buffer) => b.toString("base64url");

/** Token firmado con HMAC: `<payload>.<firma>`; el payload lleva la expiración (ms) y la «época» de sesión (cerrar sesión la incrementa y revoca todos los tokens). */
export function signSession(ttlMs: number, now = Date.now(), epoch = 0): string {
  const payload = b64u(Buffer.from(JSON.stringify({ exp: now + ttlMs, n: b64u(randomBytes(8)), e: epoch })));
  const sig = b64u(createHmac("sha256", sessionSecret()).update(payload).digest());
  return `${payload}.${sig}`;
}

export function verifySession(token: string | undefined, now = Date.now(), epoch?: number): boolean {
  if (!token) return false;
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return false;
  const good = createHmac("sha256", sessionSecret()).update(payload).digest();
  let given: Buffer;
  try {
    given = Buffer.from(sig, "base64url");
  } catch {
    return false;
  }
  if (given.length !== good.length || !timingSafeEqual(given, good)) return false;
  try {
    const { exp, e } = JSON.parse(Buffer.from(payload, "base64url").toString());
    if (epoch !== undefined && (e ?? 0) !== epoch) return false;
    return typeof exp === "number" && exp > now;
  } catch {
    return false;
  }
}

// --- contraseña: hash scrypt "scrypt$<salt b64>$<hash b64>" ----------------------------------------
const scryptAsync = (pw: string, salt: Buffer, len: number) =>
  new Promise<Buffer>((res, rej) => scrypt(pw, salt, len, { N: 16384, r: 8, p: 1 }, (e, k) => (e ? rej(e) : res(k))));

export async function hashPassword(pw: string): Promise<string> {
  const salt = randomBytes(16);
  return `scrypt$${salt.toString("base64")}$${(await scryptAsync(pw, salt, 32)).toString("base64")}`;
}

export async function verifyPassword(pw: string): Promise<boolean> {
  const stored = process.env.ADMIN_PASSWORD_HASH?.trim();
  if (stored) {
    const [kind, salt, hash] = stored.split("$");
    if (kind !== "scrypt" || !salt || !hash) return false;
    const want = Buffer.from(hash, "base64");
    const got = await scryptAsync(pw, Buffer.from(salt, "base64"), want.length);
    return want.length === got.length && timingSafeEqual(want, got);
  }
  const dev = process.env.ADMIN_PASSWORD;
  if (dev && process.env.NODE_ENV !== "production") {
    const a = Buffer.from(pw);
    const b = Buffer.from(dev);
    return a.length === b.length && timingSafeEqual(a, b);
  }
  return false; // sin contraseña configurada, nadie entra
}

// --- TOTP (RFC 6238, SHA-1, 6 dígitos, 30 s) --------------------------------------------------------
const B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
export function base32Decode(s: string): Buffer {
  const clean = s.replace(/[\s=]/g, "").toUpperCase();
  let bits = "";
  for (const ch of clean) {
    const i = B32.indexOf(ch);
    if (i < 0) throw new Error("Secreto TOTP inválido");
    bits += i.toString(2).padStart(5, "0");
  }
  const out: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) out.push(Number.parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(out);
}

export function totpCode(secretB32: string, atMs = Date.now()): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(atMs / 30000)));
  const h = createHmac("sha1", base32Decode(secretB32)).update(counter).digest();
  const o = h[h.length - 1] & 0xf;
  const n = ((h[o] & 0x7f) << 24) | (h[o + 1] << 16) | (h[o + 2] << 8) | h[o + 3];
  return String(n % 1_000_000).padStart(6, "0");
}

/** Devuelve el contador de 30 s al que corresponde el código (ventana ±1), o null si no coincide. */
export function totpMatch(code: string, secretB32: string, atMs = Date.now()): number | null {
  if (!/^\d{6}$/.test(code)) return null;
  for (const w of [-1, 0, 1]) {
    const want = Buffer.from(totpCode(secretB32, atMs + w * 30000));
    if (timingSafeEqual(want, Buffer.from(code))) return Math.floor(atMs / 30000) + w;
  }
  return null;
}

export function verifyTotp(code: string, secretB32: string, atMs = Date.now()): boolean {
  return totpMatch(code, secretB32, atMs) !== null;
}
