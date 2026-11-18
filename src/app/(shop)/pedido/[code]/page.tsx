import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { formatCop } from "@/lib/pricing";
import { STATUS_LABEL } from "@/lib/orders";
import { getSettings } from "@/lib/settings";

export const metadata: Metadata = { title: "Tu pedido", robots: { index: false } };

export default async function OrderPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const db = await getDb();
  await db.query("UPDATE orders SET status = 'expired' WHERE status = 'pending' AND reserved_until < now()");
  const [o] = await db.query<{
    id: number; code: string; status: string; customer_name: string; city: string; subtotal: number; shipping: number; total: number;
  }>("SELECT id, code, status, customer_name, city, subtotal, shipping, total FROM orders WHERE code = $1", [code.toUpperCase()]);
  if (!o) notFound();
  const items = await db.query<{ product_name: string; size: string; unit_price: number; qty: number }>(
    "SELECT product_name, size, unit_price, qty FROM order_items WHERE order_id = $1 ORDER BY id", [o.id],
  );
  const s = await getSettings(db);
  return (
    <div className="wrap section" style={{ paddingTop: "2rem" }}>
      <p className="eyebrow">Pedido</p>
      <h1 style={{ fontSize: "2.5rem" }}>{o.code}</h1>
      <p><span className={`status ${o.status}`}>{STATUS_LABEL[o.status] ?? o.status}</span></p>
      {o.status === "paid" && <p className="notice ok">¡Gracias, {o.customer_name.split(" ")[0]}! Recibirás tu chaqueta en {s.deliveryDays} días hábiles en {o.city}.</p>}
      {o.status === "pending" && <p className="notice">Estamos esperando la confirmación de tu pago.</p>}
      {(o.status === "expired" || o.status === "cancelled") && <p className="notice error">Este pedido no se completó. Puedes volver a intentarlo desde el carrito.</p>}
      <div className="summary" style={{ maxWidth: 520, marginTop: "1.5rem" }}>
        {items.map((i, k) => (
          <div className="line" key={k}><span>{i.qty} × {i.product_name} ({i.size})</span><span>{formatCop(i.unit_price * i.qty)}</span></div>
        ))}
        <div className="line"><span>Envío</span><span>{o.shipping === 0 ? "Gratis" : formatCop(o.shipping)}</span></div>
        <div className="line total"><span>Total</span><span>{formatCop(o.total)}</span></div>
      </div>
      <p className="muted" style={{ marginTop: "1.5rem" }}>Guarda este código: {o.code}.</p>
    </div>
  );
}
