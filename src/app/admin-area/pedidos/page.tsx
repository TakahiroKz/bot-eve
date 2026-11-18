import Link from "next/link";
import { adminUrl, requireAdmin } from "@/lib/admin";
import { getDb } from "@/lib/db";
import { STATUS_LABEL } from "@/lib/orders";
import { formatCop } from "@/lib/pricing";

export default async function Orders({ searchParams }: { searchParams: Promise<{ estado?: string }> }) {
  await requireAdmin();
  const { estado } = await searchParams;
  const db = await getDb();
  await db.query("UPDATE orders SET status = 'expired' WHERE status = 'pending' AND reserved_until < now()");
  const filter = estado && estado in STATUS_LABEL ? estado : "";
  const rows = await db.query<{ code: string; status: string; customer_name: string; city: string; total: number; created_at: string }>(
    `SELECT code, status, customer_name, city, total, created_at FROM orders
     ${filter ? "WHERE status = $1" : ""} ORDER BY id DESC LIMIT 200`,
    filter ? [filter] : [],
  );
  return (
    <>
      <h1 style={{ fontSize: "2rem" }}>Pedidos</h1>
      <p className="muted">
        <Link href={adminUrl("/pedidos")}>Todos</Link>
        {Object.entries(STATUS_LABEL).map(([k, v]) => <span key={k}> · <Link href={adminUrl(`/pedidos?estado=${k}`)}>{v}</Link></span>)}
      </p>
      <div className="scroll">
        <table className="table">
          <thead><tr><th>Código</th><th>Fecha</th><th>Cliente</th><th>Ciudad</th><th>Estado</th><th className="num">Total</th></tr></thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.code}>
                <td><Link href={adminUrl(`/pedidos/${o.code}`)}>{o.code}</Link></td>
                <td>{new Date(o.created_at).toLocaleString("es-CO", { timeZone: "America/Bogota" })}</td>
                <td>{o.customer_name}</td><td>{o.city}</td>
                <td><span className={`status ${o.status}`}>{STATUS_LABEL[o.status]}</span></td>
                <td className="num">{formatCop(o.total)}</td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={6} className="muted">Sin pedidos.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
