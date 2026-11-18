import { requireAdmin } from "@/lib/admin";
import { listProducts } from "@/lib/catalog";
import { saveProductAction } from "../actions";

export default async function Products({ searchParams }: { searchParams: Promise<{ error?: string; ok?: string }> }) {
  await requireAdmin();
  const { error, ok } = await searchParams;
  const products = await listProducts({ includeInactive: true });
  return (
    <>
      <h1 style={{ fontSize: "2rem" }}>Productos</h1>
      <p className="muted">Las imágenes se indican como ruta local (<code>/products/archivo.jpg</code>, dentro de <code>public/products</code>) o URL https. La primera es la principal.</p>
      {error && <p className="notice error" role="alert">{error}</p>}
      {ok && <p className="notice ok">{ok}</p>}
      <div style={{ display: "grid", gap: "2rem", marginTop: "1.5rem" }}>
        {products.map((p) => (
          <form key={p.id} action={saveProductAction} className="form wide summary">
            <input type="hidden" name="id" value={p.id} />
            <h3>{p.name} <span className="muted">· {p.gender} · {p.color}</span></h3>
            <div className="row">
              <div className="field"><label>Nombre</label><input type="text" name="name" defaultValue={p.name} required /></div>
              <div className="field"><label>Precio (COP)</label><input type="number" name="price" defaultValue={p.price} min={0} step={1000} required /></div>
            </div>
            <div className="field"><label>Frase corta</label><input type="text" name="tagline" defaultValue={p.tagline} /></div>
            <div className="field"><label>Descripción</label><textarea name="description" rows={3} defaultValue={p.description} /></div>
            <div className="field"><label>Imágenes (una por línea)</label><textarea name="images" rows={3} defaultValue={p.images.map((i) => i.url).join("\n")} /></div>
            <label><input type="checkbox" name="active" defaultChecked={p.active} /> Visible en la tienda</label>
            <div><button className="btn small" type="submit">Guardar</button></div>
          </form>
        ))}
      </div>
    </>
  );
}
