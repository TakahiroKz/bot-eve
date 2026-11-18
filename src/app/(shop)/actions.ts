"use server";

import { redirect } from "next/navigation";
import { addToCart, readCart, writeCart } from "@/lib/cart";
import { getDb } from "@/lib/db";
import { confirmPayment, createOrder, OrderError, setOrderStatus, type Customer } from "@/lib/orders";
import { getProvider } from "@/lib/payments";
import { getSettings } from "@/lib/settings";

const str = (f: FormData, k: string) => String(f.get(k) ?? "").slice(0, 300);

export async function addToCartAction(formData: FormData) {
  const slug = str(formData, "slug");
  const variantId = Number.parseInt(str(formData, "variantId"), 10);
  if (!Number.isInteger(variantId)) redirect(`/producto/${encodeURIComponent(slug)}?error=${encodeURIComponent("Elige una talla.")}`);
  const db = await getDb();
  const [v] = await db.query<{ ok: boolean }>(
    `SELECT (p.active AND v.stock - COALESCE((SELECT SUM(oi.qty) FROM order_items oi JOIN orders o ON o.id = oi.order_id
        WHERE oi.variant_id = v.id AND o.status = 'pending' AND o.reserved_until >= now()), 0) > 0) AS ok
     FROM variants v JOIN products p ON p.id = v.product_id WHERE v.id = $1`,
    [variantId],
  );
  if (!v?.ok) redirect(`/producto/${encodeURIComponent(slug)}?error=${encodeURIComponent("Esa talla no está disponible.")}`);
  await addToCart(variantId, 1);
  redirect("/carrito");
}

export async function updateCartAction(formData: FormData) {
  const variantId = Number.parseInt(str(formData, "variantId"), 10);
  const qty = Number.parseInt(str(formData, "qty"), 10);
  const lines = (await readCart()).filter((l) => l.variantId !== variantId);
  if (Number.isInteger(qty) && qty > 0) lines.push({ variantId, qty });
  await writeCart(lines);
  redirect("/carrito");
}

export async function checkoutAction(formData: FormData) {
  const customer: Customer = {
    name: str(formData, "name"), email: str(formData, "email"), phone: str(formData, "phone"),
    department: str(formData, "department"), city: str(formData, "city"), address: str(formData, "address"),
    notes: str(formData, "notes"),
  };
  let target: string;
  try {
    const db = await getDb();
    const settings = await getSettings(db);
    const provider = getProvider();
    const order = await createOrder(db, customer, await readCart(), settings, provider.name);
    const { redirectUrl } = await provider.start({ code: order.code, total: order.total, email: customer.email });
    await writeCart([]);
    target = redirectUrl;
  } catch (e) {
    if (e instanceof OrderError) redirect(`/checkout?error=${encodeURIComponent(e.message)}`);
    throw e;
  }
  redirect(target);
}

/** SOLO desarrollo: simula la respuesta de la pasarela. Con un proveedor real esto lo hace el webhook. */
export async function simulatePaymentAction(formData: FormData) {
  getProvider(); // lanza en producción
  if (getProvider().name !== "simulated") throw new Error("No disponible");
  const code = str(formData, "code");
  const db = await getDb();
  if (str(formData, "result") === "approve") await confirmPayment(db, code, `SIM-${Date.now()}`);
  else await setOrderStatus(db, code, "cancelled").catch(() => undefined);
  redirect(`/pedido/${encodeURIComponent(code)}`);
}
