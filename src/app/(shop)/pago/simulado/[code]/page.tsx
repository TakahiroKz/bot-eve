import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { formatCop } from "@/lib/pricing";
import { simulatePaymentAction } from "../../../actions";

export const metadata: Metadata = { title: "Pago simulado", robots: { index: false } };

/** SOLO desarrollo: sustituye a la pasarela de pagos hasta que se defina la real. */
export default async function SimulatedPayment({ params }: { params: Promise<{ code: string }> }) {
  if (process.env.NODE_ENV === "production" || (process.env.PAYMENTS_PROVIDER ?? "simulated") !== "simulated") notFound();
  const { code } = await params;
  const db = await getDb();
  const [o] = await db.query<{ total: number; status: string }>("SELECT total, status FROM orders WHERE code = $1", [code]);
  if (!o) notFound();
  return (
    <div className="wrap section">
      <p className="notice" style={{ marginBottom: "2rem" }}>
        Pasarela de pagos <b>simulada</b> (solo desarrollo). Aquí iría Wompi, Mercado Pago o PayU con PSE, Nequi y tarjetas.
      </p>
      <h1 style={{ fontSize: "2.2rem" }}>Pedido {code}</h1>
      <p>Total a pagar: <b>{formatCop(o.total)}</b></p>
      {o.status === "pending" ? (
        <form action={simulatePaymentAction} style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
          <input type="hidden" name="code" value={code} />
          <button className="btn accent" name="result" value="approve">Simular pago aprobado</button>
          <button className="btn ghost" name="result" value="reject">Simular pago rechazado</button>
        </form>
      ) : (
        <p className="muted">Este pedido ya no está pendiente (estado: {o.status}).</p>
      )}
    </div>
  );
}
