import { adminPath, siteUrl } from "./env";
import type { Db } from "./db";
import { emailConfig, sendEmail } from "./email";
import { adminNewOrder, customerConfirmation, type EmailContext, type EmailItem, type EmailOrder } from "./order-email";
import { confirmPayment } from "./orders";
import { getSettings } from "./settings";

type OrderRow = EmailOrder & { id: number; confirmation_sent_at: string | null };

async function context(db: Db): Promise<EmailContext> {
  const s = await getSettings(db);
  return { storeName: s.storeName, deliveryDays: s.deliveryDays, siteUrl: siteUrl(), supportEmail: s.supportEmail, whatsapp: s.whatsapp };
}

/**
 * Envía la confirmación al cliente (una sola vez, salvo `force`) y el aviso al administrador.
 * Nunca lanza: un fallo de correo no debe afectar al pago. Devuelve si el correo al cliente salió.
 */
export async function sendOrderEmails(db: Db, code: string, opts: { force?: boolean } = {}): Promise<boolean> {
  try {
    const [o] = await db.query<OrderRow>(
      `SELECT id, code, customer_name, email, phone, department, city, address, notes, subtotal, shipping, total, confirmation_sent_at
       FROM orders WHERE code = $1 AND status IN ('paid','shipped','delivered')`,
      [code],
    );
    if (!o) return false;
    if (o.confirmation_sent_at && !opts.force) return true;
    const items = await db.query<EmailItem>(
      "SELECT product_name, size, unit_price, qty FROM order_items WHERE order_id = $1 ORDER BY id",
      [o.id],
    );
    const ctx = await context(db);
    await sendEmail({ to: o.email, ...customerConfirmation(o, items, ctx) });
    await db.query("UPDATE orders SET confirmation_sent_at = now() WHERE id = $1", [o.id]);
    const admin = emailConfig().adminNotify;
    if (admin && !o.confirmation_sent_at) {
      // aviso al dueño: solo la primera vez; si falla, no se marca el pedido como no confirmado
      await sendEmail({ to: admin, ...adminNewOrder(o, items, ctx, `${siteUrl()}${adminPath()}/pedidos/${o.code}`) }).catch((e) =>
        console.error("No se pudo avisar al administrador:", (e as Error).message),
      );
    }
    return true;
  } catch (e) {
    console.error(`No se pudo enviar el correo del pedido ${code}:`, (e as Error).message);
    return false;
  }
}

/** Confirma el pago y, si es la primera vez, envía los correos. Es lo que deben llamar el webhook y la pasarela simulada. */
export async function confirmPaymentAndNotify(db: Db, code: string, paymentRef: string) {
  const result = await confirmPayment(db, code, paymentRef);
  if (result === "paid") await sendOrderEmails(db, code);
  return result;
}
