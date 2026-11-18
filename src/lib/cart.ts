import { cookies } from "next/headers";
import { getDb } from "./db";
import { MAX_LINES, MAX_PER_LINE, normalizeLines, type CartLine } from "./orders";
import { computeTotals, type Totals } from "./pricing";
import { getSettings } from "./settings";

const COOKIE = "cart";

export async function readCart(): Promise<CartLine[]> {
  const raw = (await cookies()).get(COOKIE)?.value;
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw) as { v?: unknown; q?: unknown }[];
    if (!Array.isArray(arr)) return [];
    return normalizeLines(arr.slice(0, MAX_LINES).map((x) => ({ variantId: Number(x.v), qty: Number(x.q) })));
  } catch {
    return [];
  }
}

export async function writeCart(lines: CartLine[]): Promise<void> {
  const clean = normalizeLines(lines);
  (await cookies()).set(COOKIE, JSON.stringify(clean.map((l) => ({ v: l.variantId, q: l.qty }))), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 14,
  });
}

export async function addToCart(variantId: number, qty = 1): Promise<void> {
  const lines = await readCart();
  const cur = lines.find((l) => l.variantId === variantId);
  if (cur) cur.qty = Math.min(MAX_PER_LINE, cur.qty + qty);
  else lines.push({ variantId, qty });
  await writeCart(lines);
}

export interface CartView {
  lines: { variantId: number; qty: number; name: string; size: string; color: string; unitPrice: number; image: string; slug: string; available: number }[];
  totals: Totals;
}

/** Carrito con precios y disponibilidad tomados de la base de datos (nunca de la cookie). */
export async function cartView(): Promise<CartView> {
  const db = await getDb();
  const lines = await readCart();
  const settings = await getSettings(db);
  if (!lines.length) return { lines: [], totals: computeTotals([], settings) };
  const rows = await db.query<{
    id: number; size: string; stock: number; name: string; color: string; price: number; slug: string; image: string | null; reserved: number;
  }>(
    `SELECT v.id, v.size, v.stock, p.name, p.color, p.price, p.slug,
            (SELECT url FROM product_images i WHERE i.product_id = p.id ORDER BY position, id LIMIT 1) AS image,
            COALESCE((SELECT SUM(oi.qty) FROM order_items oi JOIN orders o ON o.id = oi.order_id
                      WHERE oi.variant_id = v.id AND o.status = 'pending' AND o.reserved_until >= now()), 0)::int AS reserved
     FROM variants v JOIN products p ON p.id = v.product_id
     WHERE v.id = ANY($1::int[]) AND p.active`,
    [lines.map((l) => l.variantId)],
  );
  const view = lines.flatMap((l) => {
    const r = rows.find((x) => x.id === l.variantId);
    if (!r) return [];
    return [{
      variantId: l.variantId, qty: l.qty, name: r.name, size: r.size, color: r.color, unitPrice: r.price,
      image: r.image ?? "", slug: r.slug, available: Math.max(0, r.stock - r.reserved),
    }];
  });
  return { lines: view, totals: computeTotals(view.map((v) => ({ unitPrice: v.unitPrice, qty: v.qty })), settings) };
}
