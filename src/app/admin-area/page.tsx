import Link from "next/link";
import { adminUrl, requireAdmin } from "@/lib/admin";
import { getDb } from "@/lib/db";
import { STATUS_LABEL } from "@/lib/orders";
import { formatCop } from "@/lib/pricing";

export default async function Dashboard() {
  await requireAdmin();
  const db = await getDb();
  await db.query("UPDATE orders SET status = 'expired' WHERE status = 'pending' AND reserved_until < now()");
  const [stats] = await db.query<{ paid: number; revenue: number; to_ship: number; low: number }>(
    `SELECT (SELECT COUNT(*) FROM orders WHERE status IN ('paid','shipped','delivered'))::int AS paid,
            (SELECT COALESCE(SUM(total),0) FROM orders WHERE status IN ('paid','shipped','delivered'))::int AS revenue,
            (SELECT COUNT(*) FROM orders WHERE status = 'paid')::int AS to_ship,
            (SELECT COUNT(*) FROM variants WHERE stock <= 1)::int AS low`,
  );
  const recent = await db.query<{ code: string; status: string; customer_name: string; total: number; created_at: string }>(
    "SELECT code, status, customer_name, total, created_at FROM orders ORDER BY id DESC LIMIT 8",
  );
  return (
    <>
      <h1 style={{ fontSize: "2rem" }}>Resumen</h1>
      <div className="cards">
        <div className="stat"><b>{stats.to_ship}</b>Por enviar</div>
        <div className="stat"><b>{stats.paid}</b>Pedidos pagados</div>
        <div className="stat"><b>{formatCop(stats.revenue)}</b>Ventas</div>
        <div className="stat"><b>{stats.low}</b>Tallas con stock ≤ 1</div>
      </div>
      <h2 style={{ fontSize: "1.2rem" }}>Últimos pedidos</h2>
      <div className="scroll">
        <table className="table">
          <thead><tr><th>Código</th><th>Cliente</th><th>Estado</th><th className="num">Total</th></tr></thead>
          <tbody>
            {recent.map((o) => (
              <tr key={o.code}>
                <td><Link href={adminUrl(`/pedidos/${o.code}`)}>{o.code}</Link></td>
                <td>{o.customer_name}</td>
                <td><span className={`status ${o.status}`}>{STATUS_LABEL[o.status]}</span></td>
                <td className="num">{formatCop(o.total)}</td>
              </tr>
            ))}
            {!recent.length && <tr><td colSpan={4} className="muted">Aún no hay pedidos.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
