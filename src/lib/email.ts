import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Envío de correo detrás de una interfaz. El proveedor se elige con `EMAIL_PROVIDER`:
 *   console (por defecto en desarrollo): escribe el correo en .data/outbox/ y lo imprime
 *   resend | brevo: envío real por API (requieren la clave y el dominio verificado con SPF/DKIM)
 *   memory: solo para pruebas
 */
export interface EmailMessage {
  to: string;
  subject: string;
  html: string;
  text: string;
  replyTo?: string;
}

export class EmailError extends Error {}

export const memoryOutbox: EmailMessage[] = [];

export interface EmailConfig {
  provider: string;
  from: string;
  replyTo: string;
  adminNotify: string;
}

export function emailConfig(): EmailConfig {
  return {
    provider: (process.env.EMAIL_PROVIDER ?? "console").trim().toLowerCase(),
    from: process.env.EMAIL_FROM?.trim() || "Nerova <pedidos@example.com>",
    replyTo: process.env.EMAIL_REPLY_TO?.trim() ?? "",
    adminNotify: process.env.EMAIL_ADMIN_NOTIFY?.trim() ?? "",
  };
}

const addr = (from: string) => from.match(/<([^>]+)>/)?.[1] ?? from;

async function postJson(url: string, headers: Record<string, string>, body: unknown): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok) {
    // No se registra el cuerpo completo (puede contener datos del cliente); solo el estado.
    throw new EmailError(`El proveedor de correo respondió ${res.status}`);
  }
}

export async function sendEmail(msg: EmailMessage): Promise<void> {
  const cfg = emailConfig();
  const replyTo = msg.replyTo || cfg.replyTo || undefined;
  switch (cfg.provider) {
    case "memory":
      memoryOutbox.push(msg);
      return;
    case "console": {
      if (process.env.NODE_ENV === "production") {
        throw new EmailError("EMAIL_PROVIDER=console no sirve en producción; configura resend o brevo.");
      }
      const dir = join(process.cwd(), ".data", "outbox");
      mkdirSync(dir, { recursive: true });
      const file = join(dir, `${Date.now()}-${msg.to.replace(/[^a-z0-9@.]/gi, "_")}.html`);
      writeFileSync(file, msg.html, "utf8");
      console.log(`[correo simulado] para ${msg.to}: ${msg.subject} -> ${file}`);
      return;
    }
    case "resend": {
      const key = process.env.RESEND_API_KEY;
      if (!key) throw new EmailError("Falta RESEND_API_KEY");
      await postJson(
        "https://api.resend.com/emails",
        { Authorization: `Bearer ${key}` },
        { from: cfg.from, to: [msg.to], subject: msg.subject, html: msg.html, text: msg.text, ...(replyTo ? { reply_to: replyTo } : {}) },
      );
      return;
    }
    case "brevo": {
      const key = process.env.BREVO_API_KEY;
      if (!key) throw new EmailError("Falta BREVO_API_KEY");
      const m = cfg.from.match(/^(.*)<([^>]+)>$/);
      await postJson(
        "https://api.brevo.com/v3/smtp/email",
        { "api-key": key },
        {
          sender: { name: m ? m[1].trim() : "Nerova", email: addr(cfg.from) },
          to: [{ email: msg.to }],
          subject: msg.subject,
          htmlContent: msg.html,
          textContent: msg.text,
          ...(replyTo ? { replyTo: { email: replyTo } } : {}),
        },
      );
      return;
    }
    default:
      throw new EmailError(`Proveedor de correo desconocido: ${cfg.provider}`);
  }
}
