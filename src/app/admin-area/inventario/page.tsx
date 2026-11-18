import { requireAdmin } from "@/lib/admin";
import { listProducts } from "@/lib/catalog";
import { saveStockAction } from "../actions";

export default async function Inventory({ searchParams }: { searchParams: Promise<{ error?: string; ok?: string }> }) {
  await requireAdmin();
  const { error, ok } = await searchParams;
  const products = await listProducts({ includeInactive: true });
  return (
    <>
      <h1 style={{ fontSize: "2rem" }}>Inventario</h1>
      <p className="muted">«Reservado» son unidades retenidas 15 minutos por pedidos que aún no se pagan.</p>
      {error && <p className="notice error" role="alert">{error}</p>}
      {ok && <p className="notice ok">{ok}</p>}
      <div className="scroll">
        <table className="table">
          <thead><tr><th>Producto</th><th>Talla</th><th>Reservado</th><th>Stock</th><th></th></tr></thead>
          <tbody>
            {products.flatMap((p) =>
              p.variants.map((v) => (
                <tr key={v.id}>
                  <td>{p.name} <span className="muted">· {p.color} · {p.gender}</span></td>
                  <td>{v.size}</td>
                  <td>{v.stock - v.available}</td>
                  <td colSpan={2}>
                    <form action={saveStockAction} className="qty">
                      <input type="hidden" name="id" value={v.id} />
                      <input type="number" name="stock" min={0} defaultValue={v.stock} aria-label={`Stock de ${p.name} talla ${v.size}`} />
                      <button className="btn small" type="submit">Guardar</button>
                    </form>
                  </td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
