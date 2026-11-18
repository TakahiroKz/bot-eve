// Genera el hash scrypt para ADMIN_PASSWORD_HASH y un secreto TOTP nuevo.
//   npm run admin:hash -- "tu contraseña"
import { randomBytes, scryptSync } from "node:crypto";

const pw = process.argv[2];
if (!pw || pw.length < 12) {
  console.error('Uso: npm run admin:hash -- "contraseña de al menos 12 caracteres"');
  process.exit(1);
}
const salt = randomBytes(16);
const hash = scryptSync(pw, salt, 32, { N: 16384, r: 8, p: 1 });
console.log("ADMIN_PASSWORD_HASH=" + `scrypt$${salt.toString("base64")}$${hash.toString("base64")}`);

const B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
let bits = "";
for (const b of randomBytes(20)) bits += b.toString(2).padStart(8, "0");
let secret = "";
for (let i = 0; i < bits.length; i += 5) secret += B32[parseInt(bits.slice(i, i + 5), 2)];
console.log("ADMIN_TOTP_SECRET=" + secret + "   # opcional: agrégalo a tu app de autenticación (Google Authenticator, etc.)");
