import type { Metadata } from "next";
import Link from "next/link";
import { cartView } from "@/lib/cart";
import { formatCop } from "@/lib/pricing";
import { getSettings } from "@/lib/settings";
import { updateCartAction } from "../actions";

export const metadata: Metadata = { title: "Tu carrito", robots: { index: false } };

export default async function CartPage() {
  const [{ lines, totals }, s] = await Promise.all([cartView(), getSettings()]);
  if (!lines.length) {
    return (
      <div className="wrap section">
        <h1 style={{ fontSize: "2.5rem" }}>Tu carrito está vacío.</h1>
        <p className="muted">La chaqueta correcta te está esperando.</p>
        <Link href="/hombre" className="btn">Hombre</Link>{" "}
        <Link href="/mujer" className="btn ghost">Mujer</Link>
      </div>
    );
  }
  const missing = s.freeShippingMinItems - totals.itemCount;
  const short = lines.some((l) => l.qty > l.available);
  return (
    <div className="wrap section" style={{ paddingTop: "2rem" }}>
      <h1 style={{ fontSize: "2.5rem" }}>Tu carrito</h1>
      <div className="two">
        <div className="scroll">
          <table className="table">
            <thead><tr><th></th><th>Producto</th><th>Cantidad</th><th className="num">Precio</th></tr></thead>
            <tbody>
              {lines.map((l) => (
                <tr key={l.variantId}>
                  <td>{l.image && /* eslint-disable-next-line @next/next/no-img-element */ <img src={l.image} alt="" />}</td>
                  <td>
                    <Link href={`/producto/${l.slug}`}><b>{l.name}</b></Link>
                    <div className="muted">{l.color} · talla {l.size}</div>
                    {l.qty > l.available && <div className="notice error" style={{ marginTop: ".4rem" }}>Solo quedan {l.available}.</div>}
                  </td>
                  <td>
                    <form action={updateCartAction} className="qty">
                      <input type="hidden" name="variantId" value={l.variantId} />
                      <input type="number" name="qty" min={0} max={5} defaultValue={l.qty} aria-label={`Cantidad de ${l.name}`} />
                      <button className="link-btn" type="submit">Actualizar</button>
                    </form>
                  </td>
                  <td className="num">{formatCop(l.unitPrice * l.qty)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted" style={{ marginTop: "1rem" }}>Pon la cantidad en 0 para quitar una prenda.</p>
        </div>
        <aside className="summary">
          <div className="line"><span>Subtotal</span><span>{formatCop(totals.subtotal)}</span></div>
          <div className="line"><span>Envío</span><span>{totals.freeShipping ? "Gratis" : formatCop(totals.shipping)}</span></div>
          {!totals.freeShipping && missing > 0 && (
            <p className="notice ok">Añade {missing} prenda{missing > 1 ? "s" : ""} más y el envío es gratis.</p>
          )}
          <div className="line total"><span>Total</span><span>{formatCop(totals.total)}</span></div>
          {short ? (
            <p className="notice error">Ajusta las cantidades para continuar.</p>
          ) : (
            <Link href="/checkout" className="btn accent" style={{ textAlign: "center" }}>Continuar</Link>
          )}
        </aside>
      </div>
    </div>
  );
}
