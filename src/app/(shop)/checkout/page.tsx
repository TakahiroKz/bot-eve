import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { cartView } from "@/lib/cart";
import { formatCop } from "@/lib/pricing";
import { checkoutAction } from "../actions";

export const metadata: Metadata = { title: "Finalizar compra", robots: { index: false } };

type Props = { searchParams: Promise<{ error?: string }> };

export default async function Checkout({ searchParams }: Props) {
  const { error } = await searchParams;
  const { lines, totals } = await cartView();
  if (!lines.length) redirect("/carrito");
  return (
    <div className="wrap section" style={{ paddingTop: "2rem" }}>
      <h1 style={{ fontSize: "2.5rem" }}>Finalizar compra</h1>
      <div className="two">
        <form action={checkoutAction} className="form">
          {error && <p className="notice error" role="alert">{error}</p>}
          <div className="field"><label htmlFor="name">Nombre completo</label><input id="name" name="name" type="text" required autoComplete="name" /></div>
          <div className="row">
            <div className="field"><label htmlFor="email">Correo</label><input id="email" name="email" type="email" required autoComplete="email" /></div>
            <div className="field"><label htmlFor="phone">Celular</label><input id="phone" name="phone" type="tel" required autoComplete="tel" /></div>
          </div>
          <div className="row">
            <div className="field"><label htmlFor="department">Departamento</label><input id="department" name="department" type="text" required autoComplete="address-level1" /></div>
            <div className="field"><label htmlFor="city">Ciudad</label><input id="city" name="city" type="text" required autoComplete="address-level2" /></div>
          </div>
          <div className="field"><label htmlFor="address">Dirección de entrega</label><input id="address" name="address" type="text" required autoComplete="street-address" /></div>
          <div className="field"><label htmlFor="notes">Indicaciones (opcional)</label><textarea id="notes" name="notes" rows={3} maxLength={500} /></div>
          <div className="field">
            <label htmlFor="accept" style={{ display: "flex", gap: ".6rem", alignItems: "flex-start", textTransform: "none", letterSpacing: 0 }}>
              <input id="accept" name="accept" type="checkbox" required style={{ width: "auto", marginTop: ".25rem" }} />
              <span>
                Acepto los <Link href="/politicas/terminos" target="_blank">términos y condiciones</Link> y autorizo el tratamiento de mis datos
                según la <Link href="/politicas/datos" target="_blank">política de datos personales</Link>.
              </span>
            </label>
          </div>
          <p className="muted" style={{ fontSize: ".9rem" }}>
            Al continuar reservamos tus prendas por 15 minutos mientras pagas.
          </p>
          <button className="btn accent" type="submit">Ir a pagar · {formatCop(totals.total)}</button>
        </form>
        <aside className="summary">
          {lines.map((l) => (
            <div className="line" key={l.variantId}>
              <span>{l.qty} × {l.name} ({l.size})</span><span>{formatCop(l.unitPrice * l.qty)}</span>
            </div>
          ))}
          <div className="line"><span>Envío</span><span>{totals.freeShipping ? "Gratis" : formatCop(totals.shipping)}</span></div>
          <div className="line total"><span>Total</span><span>{formatCop(totals.total)}</span></div>
        </aside>
      </div>
    </div>
  );
}
