import Link from "next/link";
import { notFound } from "next/navigation";
import { adminUrl, requireAdmin } from "@/lib/admin";
import { getDb } from "@/lib/db";
import { nextStatuses, STATUS_LABEL } from "@/lib/orders";
import { formatCop } from "@/lib/pricing";
import { setStatusAction } from "../../actions";

type Props = { params: Promise<{ code: string }>; searchParams: Promise<{ error?: string; ok?: string }> };

export default async function OrderDetail({ params, searchParams }: Props) {
  await requireAdmin();
  const { code } = await params;
  const { error, ok } = await searchParams;
  const db = await getDb();
  const [o] = await db.query<{
    id: number; code: string; status: string; customer_name: string; email: string; phone: string; department: string; city: string;
    address: string; notes: string; subtotal: number; shipping: number; total: number; payment_provider: string; payment_ref: string;
    created_at: string; paid_at: string | null;
  }>("SELECT * FROM orders WHERE code = $1", [code]);
  if (!o) notFound();
  const items = await db.query<{ product_name: string; size: string; unit_price: number; qty: number }>(
    "SELECT product_name, size, unit_price, qty FROM order_items WHERE order_id = $1 ORDER BY id", [o.id],
  );
  return (
    <>
      <p><Link href={adminUrl("/pedidos")} className="muted">← Pedidos</Link></p>
      <h1 style={{ fontSize: "2rem" }}>Pedido {o.code} <span className={`status ${o.status}`}>{STATUS_LABEL[o.status]}</span></h1>
      {error && <p className="notice error" role="alert">{error}</p>}
      {ok && <p className="notice ok">{ok}</p>}
      <div className="two">
        <div>
          <h2 style={{ fontSize: "1.1rem" }}>Entrega</h2>
          <p>{o.customer_name}<br />{o.address}, {o.city}, {o.department}<br />{o.phone} · {o.email}</p>
          {o.notes && <p className="notice">{o.notes}</p>}
          <p className="muted">Pasarela: {o.payment_provider || "—"} · Ref.: {o.payment_ref || "—"}</p>
          <h2 style={{ fontSize: "1.1rem" }}>Cambiar estado</h2>
          <div style={{ display: "flex", gap: ".6rem", flexWrap: "wrap" }}>
            {nextStatuses(o.status).map((st) => (
              <form key={st} action={setStatusAction}>
                <input type="hidden" name="code" value={o.code} />
                <button className={`btn small ${st === "cancelled" ? "danger" : ""}`} name="status" value={st}>{STATUS_LABEL[st]}</button>
              </form>
            ))}
            {!nextStatuses(o.status).length && <span className="muted">Sin cambios posibles.</span>}
          </div>
          <p className="muted" style={{ fontSize: ".85rem", marginTop: "1rem" }}>Cancelar un pedido pagado devuelve las prendas al inventario.</p>
        </div>
        <aside className="summary">
          {items.map((i, k) => <div className="line" key={k}><span>{i.qty} × {i.product_name} ({i.size})</span><span>{formatCop(i.unit_price * i.qty)}</span></div>)}
          <div className="line"><span>Envío</span><span>{formatCop(o.shipping)}</span></div>
          <div className="line total"><span>Total</span><span>{formatCop(o.total)}</span></div>
        </aside>
      </div>
    </>
  );
}
