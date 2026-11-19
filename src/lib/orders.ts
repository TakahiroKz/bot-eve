import { randomInt } from "node:crypto";
import type { Db, Row } from "./db";
import { computeTotals, type PricingSettings } from "./pricing";

export const RESERVATION_MINUTES = 15;
export const MAX_PER_LINE = 5;
export const MAX_LINES = 10;

export interface CartLine {
  variantId: number;
  qty: number;
}

export interface Customer {
  name: string;
  email: string;
  phone: string;
  department: string;
  city: string;
  address: string;
  notes: string;
}

export class OrderError extends Error {}

const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
export function newOrderCode(): string {
  let s = "";
  for (let i = 0; i < 8; i++) s += CODE_ALPHABET[randomInt(CODE_ALPHABET.length)];
  return s;
}

const EMAIL_RE = /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*\.[A-Za-z]{2,}$/;
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/; // saltos de línea y otros caracteres de control (inyección en cabeceras de correo)

export function validateCustomer(c: Customer): string | null {
  const email = c.email.trim();
  if (c.name.trim().length < 3 || c.name.length > 120) return "Escribe tu nombre completo.";
  if (email.length > 254 || !EMAIL_RE.test(email)) return "Escribe un correo válido.";
  if (!/^\+?\d[\d\s-]{6,14}$/.test(c.phone.trim())) return "Escribe un teléfono válido.";
  if (c.department.trim().length < 3 || c.city.trim().length < 2) return "Indica departamento y ciudad.";
  if (c.address.trim().length < 6) return "Escribe una dirección de entrega completa.";
  if ([c.name, c.email, c.phone, c.department, c.city, c.address].some((v) => CONTROL_CHARS.test(v))) {
    return "Hay caracteres no permitidos en el formulario.";
  }
  return null;
}

/** Junta líneas repetidas y descarta cantidades inválidas. */
export function normalizeLines(lines: CartLine[]): CartLine[] {
  const m = new Map<number, number>();
  for (const l of lines) {
    if (!Number.isInteger(l.variantId) || !Number.isInteger(l.qty) || l.qty < 1) continue;
    m.set(l.variantId, Math.min(MAX_PER_LINE, (m.get(l.variantId) ?? 0) + l.qty));
  }
  return [...m].slice(0, MAX_LINES).map(([variantId, qty]) => ({ variantId, qty }));
}

/**
 * Crea un pedido pendiente y reserva el stock durante `RESERVATION_MINUTES`.
 * Los precios salen siempre de la base de datos. Bloquea las variantes para evitar doble venta.
 */
export async function createOrder(
  db: Db,
  customer: Customer,
  rawLines: CartLine[],
  pricing: PricingSettings,
  provider: string,
): Promise<{ code: string; total: number }> {
  const err = validateCustomer(customer);
  if (err) throw new OrderError(err);
  const lines = normalizeLines(rawLines);
  if (!lines.length) throw new OrderError("Tu carrito está vacío.");

  return db.tx(async (q) => {
    await q("UPDATE orders SET status = 'expired' WHERE status = 'pending' AND reserved_until < now()");
    const ids = lines.map((l) => l.variantId);
    const vars = await q<Row & { id: number; size: string; stock: number; name: string; price: number; active: boolean }>(
      `SELECT v.id, v.size, v.stock, p.name, p.price, p.active
       FROM variants v JOIN products p ON p.id = v.product_id
       WHERE v.id = ANY($1::int[]) ORDER BY v.id FOR UPDATE OF v`,
      [ids],
    );
    const priced: { v: (typeof vars)[number]; qty: number }[] = [];
    for (const l of lines) {
      const v = vars.find((x) => x.id === l.variantId);
      if (!v || !v.active) throw new OrderError("Un producto de tu carrito ya no está disponible.");
      const [{ reserved }] = await q<{ reserved: number }>(
        `SELECT COALESCE(SUM(oi.qty), 0)::int AS reserved FROM order_items oi JOIN orders o ON o.id = oi.order_id
         WHERE oi.variant_id = $1 AND o.status = 'pending' AND o.reserved_until >= now()`,
        [l.variantId],
      );
      if (v.stock - reserved < l.qty) {
        throw new OrderError(`No hay stock suficiente de ${v.name} (talla ${v.size}).`);
      }
      priced.push({ v, qty: l.qty });
    }
    const totals = computeTotals(
      priced.map((p) => ({ unitPrice: p.v.price, qty: p.qty })),
      pricing,
    );
    let code = newOrderCode();
    for (let i = 0; i < 5 && (await q("SELECT 1 FROM orders WHERE code = $1", [code])).length; i++) code = newOrderCode();
    const [{ id }] = await q<{ id: number }>(
      `INSERT INTO orders (code, customer_name, email, phone, department, city, address, notes,
                           subtotal, shipping, total, payment_provider, reserved_until)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12, now() + ($13 || ' minutes')::interval) RETURNING id`,
      [
        code, customer.name.trim(), customer.email.trim().toLowerCase(), customer.phone.trim(),
        customer.department.trim(), customer.city.trim(), customer.address.trim(), customer.notes.trim().slice(0, 500),
        totals.subtotal, totals.shipping, totals.total, provider, String(RESERVATION_MINUTES),
      ],
    );
    for (const p of priced) {
      await q(
        "INSERT INTO order_items (order_id, variant_id, product_name, size, unit_price, qty) VALUES ($1,$2,$3,$4,$5,$6)",
        [id, p.v.id, p.v.name, p.v.size, p.v.price, p.qty],
      );
    }
    return { code, total: totals.total };
  });
}

/**
 * Confirma un pago (llamado SOLO desde el webhook/proveedor, nunca desde el navegador del cliente).
 * Idempotente. Descuenta el stock. Si la reserva venció y ya no hay stock, el pedido queda pagado con
 * una alerta en las notas para revisar o reembolsar.
 */
export async function confirmPayment(db: Db, code: string, paymentRef: string): Promise<"paid" | "already" | "missing"> {
  return db.tx(async (q) => {
    const [o] = await q<{ id: number; status: string }>("SELECT id, status FROM orders WHERE code = $1 FOR UPDATE", [code]);
    if (!o) return "missing";
    if (["paid", "shipped", "delivered"].includes(o.status)) return "already";
    const items = await q<{ variant_id: number; qty: number }>("SELECT variant_id, qty FROM order_items WHERE order_id = $1", [o.id]);
    let alert = o.status === "cancelled" ? " [ALERTA: pago recibido sobre un pedido cancelado; revisar o reembolsar]" : "";
    for (const it of items) {
      const [v] = await q<{ stock: number }>("SELECT stock FROM variants WHERE id = $1 FOR UPDATE", [it.variant_id]);
      if (v.stock < it.qty) alert = " [ALERTA: pago recibido sin stock suficiente; revisar o reembolsar]";
      await q("UPDATE variants SET stock = GREATEST(stock - $2, 0) WHERE id = $1", [it.variant_id, it.qty]);
    }
    await q(
      "UPDATE orders SET status = 'paid', paid_at = now(), payment_ref = $2, reserved_until = NULL, notes = notes || $3 WHERE id = $1",
      [o.id, paymentRef, alert],
    );
    return "paid";
  });
}

const FLOW: Record<string, string[]> = {
  pending: ["cancelled"],
  paid: ["shipped", "cancelled"],
  shipped: ["delivered", "cancelled"],
  delivered: [],
  cancelled: [],
  expired: [],
};

/** Cambio de estado desde el panel. Cancelar un pedido pagado devuelve el stock. */
export async function setOrderStatus(db: Db, code: string, next: string): Promise<void> {
  await db.tx(async (q) => {
    const [o] = await q<{ id: number; status: string }>("SELECT id, status FROM orders WHERE code = $1 FOR UPDATE", [code]);
    if (!o) throw new OrderError("Pedido no encontrado.");
    if (!FLOW[o.status]?.includes(next)) throw new OrderError(`No se puede pasar de ${o.status} a ${next}.`);
    if (next === "cancelled" && ["paid", "shipped"].includes(o.status)) {
      await q(
        `UPDATE variants v SET stock = v.stock + oi.qty FROM order_items oi
         WHERE oi.order_id = $1 AND oi.variant_id = v.id`,
        [o.id],
      );
    }
    await q("UPDATE orders SET status = $2, reserved_until = NULL WHERE id = $1", [o.id, next]);
  });
}

export const nextStatuses = (status: string): string[] => FLOW[status] ?? [];

export const STATUS_LABEL: Record<string, string> = {
  pending: "Pendiente de pago",
  paid: "Pagado",
  shipped: "Enviado",
  delivered: "Entregado",
  cancelled: "Cancelado",
  expired: "Expirado",
};
