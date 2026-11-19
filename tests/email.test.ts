import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { memoryDb, type Db } from "../src/lib/db";
import { EmailError, memoryOutbox, sendEmail } from "../src/lib/email";
import { esc } from "../src/lib/order-email";
import { confirmPaymentAndNotify, sendOrderEmails } from "../src/lib/notifications";
import { createOrder, type Customer } from "../src/lib/orders";
import { seedIfEmpty } from "../src/lib/seed";

const PRICING = { shippingFee: 15000, freeShippingMinItems: 2 };
const CUSTOMER: Customer = {
  name: "Ana <b>Pérez</b>", email: "ana@example.com", phone: "3001234567",
  department: "Antioquia", city: "Medellín", address: 'Calle 10 # 20-30 "torre" <script>x</script>', notes: "",
};
let db: Db;

async function newOrder() {
  const [v] = await db.query<{ id: number }>("SELECT v.id FROM variants v JOIN products p ON p.id = v.product_id WHERE p.slug = 'ferro-hombre' AND v.size = 'M'");
  return createOrder(db, CUSTOMER, [{ variantId: v.id, qty: 1 }], PRICING, "simulated");
}

beforeEach(async () => {
  process.env.EMAIL_PROVIDER = "memory";
  process.env.EMAIL_ADMIN_NOTIFY = "dueno@example.com";
  memoryOutbox.length = 0;
  db = await memoryDb();
  await seedIfEmpty(db);
});
afterEach(() => {
  delete process.env.EMAIL_PROVIDER;
  delete process.env.EMAIL_ADMIN_NOTIFY;
  delete process.env.RESEND_API_KEY;
  delete process.env.BREVO_API_KEY;
  vi.restoreAllMocks();
});

describe("correo de confirmación", () => {
  it("al pagar se envía la confirmación al cliente y el aviso al dueño, una sola vez", async () => {
    const o = await newOrder();
    await confirmPaymentAndNotify(db, o.code, "ref");
    expect(memoryOutbox.map((m) => m.to)).toEqual(["ana@example.com", "dueno@example.com"]);
    expect(memoryOutbox[0].subject).toContain(o.code);
    expect(memoryOutbox[0].text).toContain("3 días hábiles");
    await confirmPaymentAndNotify(db, o.code, "ref"); // pago repetido (webhook duplicado)
    expect(memoryOutbox).toHaveLength(2);
  });

  it("escapa el HTML que escribe el cliente", async () => {
    const o = await newOrder();
    await confirmPaymentAndNotify(db, o.code, "ref");
    for (const m of memoryOutbox) {
      expect(m.html).not.toContain("<script>");
      expect(m.html).not.toContain("<b>Pérez</b>");
    }
    expect(memoryOutbox[0].html).toContain("&lt;script&gt;");
    expect(esc(`<a href="x">&'`)).toBe("&lt;a href=&quot;x&quot;&gt;&amp;&#39;");
  });

  it("un pedido sin pagar no genera correo", async () => {
    const o = await newOrder();
    expect(await sendOrderEmails(db, o.code)).toBe(false);
    expect(memoryOutbox).toHaveLength(0);
  });

  it("si el proveedor falla, el pago sigue confirmado y se puede reenviar", async () => {
    const o = await newOrder();
    process.env.EMAIL_PROVIDER = "resend"; // sin RESEND_API_KEY: falla
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(await confirmPaymentAndNotify(db, o.code, "ref")).toBe("paid");
    const [row] = await db.query<{ status: string; confirmation_sent_at: string | null }>("SELECT status, confirmation_sent_at FROM orders WHERE code = $1", [o.code]);
    expect(row.status).toBe("paid");
    expect(row.confirmation_sent_at).toBeNull();
    process.env.EMAIL_PROVIDER = "memory";
    expect(await sendOrderEmails(db, o.code, { force: true })).toBe(true);
    expect(memoryOutbox[0].to).toBe("ana@example.com");
  });
});

describe("proveedores", () => {
  it("Resend: endpoint, clave y cuerpo correctos", async () => {
    process.env.EMAIL_PROVIDER = "resend";
    process.env.RESEND_API_KEY = "re_test";
    process.env.EMAIL_FROM = "Nerova <pedidos@nerova.example>";
    process.env.EMAIL_REPLY_TO = "hola@nerova.example";
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));
    await sendEmail({ to: "a@b.co", subject: "S", html: "<p>h</p>", text: "t" });
    const [url, init] = f.mock.calls[0];
    expect(url).toBe("https://api.resend.com/emails");
    expect((init!.headers as Record<string, string>).Authorization).toBe("Bearer re_test");
    expect(JSON.parse(init!.body as string)).toMatchObject({ from: "Nerova <pedidos@nerova.example>", to: ["a@b.co"], subject: "S", reply_to: "hola@nerova.example" });
  });

  it("Brevo: formato propio y errores sin filtrar el contenido", async () => {
    process.env.EMAIL_PROVIDER = "brevo";
    process.env.BREVO_API_KEY = "xkeysib-test";
    process.env.EMAIL_FROM = "Nerova <pedidos@nerova.example>";
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("secreto del cliente", { status: 401 }));
    await expect(sendEmail({ to: "a@b.co", subject: "S", html: "h", text: "t" })).rejects.toThrow(/401/);
    const err = await sendEmail({ to: "a@b.co", subject: "S", html: "h", text: "t" }).catch((e: Error) => e);
    expect((err as Error).message).not.toContain("secreto");
    const body = JSON.parse(f.mock.calls[0][1]!.body as string);
    expect(body).toMatchObject({ sender: { name: "Nerova", email: "pedidos@nerova.example" }, to: [{ email: "a@b.co" }], htmlContent: "h" });
  });

  it("claves faltantes, proveedor desconocido y consola en producción", async () => {
    process.env.EMAIL_PROVIDER = "resend";
    await expect(sendEmail({ to: "a@b.co", subject: "S", html: "h", text: "t" })).rejects.toThrow(EmailError);
    process.env.EMAIL_PROVIDER = "otro";
    await expect(sendEmail({ to: "a@b.co", subject: "S", html: "h", text: "t" })).rejects.toThrow(/desconocido/);
    process.env.EMAIL_PROVIDER = "console";
    vi.stubEnv("NODE_ENV", "production");
    await expect(sendEmail({ to: "a@b.co", subject: "S", html: "h", text: "t" })).rejects.toThrow(/producción/);
    vi.unstubAllEnvs();
  });
});
