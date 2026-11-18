import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getProduct } from "@/lib/catalog";
import { formatCop } from "@/lib/pricing";
import { getSettings } from "@/lib/settings";
import { addToCartAction } from "../../actions";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<{ error?: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const p = await getProduct((await params).slug);
  return p ? { title: `${p.name} · chaqueta de cuero ${p.color.toLowerCase()}`, description: p.tagline } : {};
}

export default async function ProductPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const { error } = await searchParams;
  const [p, s] = await Promise.all([getProduct(slug), getSettings()]);
  if (!p) notFound();
  const free = s.freeShippingMinItems;
  return (
    <div className="wrap section" style={{ paddingTop: "2rem" }}>
      <div className="product">
        <div className="gallery">
          {p.images.map((img) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={img.url} src={img.url} alt={img.alt} />
          ))}
        </div>
        <div className="product-info">
          <p className="eyebrow">{p.gender === "hombre" ? "Hombre" : "Mujer"} · {p.color}</p>
          <h1 style={{ fontSize: "clamp(2rem,4vw,3rem)" }}>{p.name}</h1>
          <p style={{ fontSize: "1.15rem" }}>{p.tagline}</p>
          <p className="muted">{p.description}</p>
          <div className="price">{formatCop(p.price)}</div>
          {error && <p className="notice error" role="alert">{error}</p>}
          <form action={addToCartAction}>
            <input type="hidden" name="slug" value={p.slug} />
            <fieldset className="sizes">
              <legend className="eyebrow" style={{ marginBottom: ".6rem" }}>Talla</legend>
              {p.variants.map((v) => (
                <label key={v.id} title={v.available === 0 ? "Agotada" : undefined}>
                  <input type="radio" name="variantId" value={v.id} disabled={v.available === 0} required />
                  <span>{v.size}</span>
                </label>
              ))}
            </fieldset>
            <button className="btn accent" type="submit" disabled={p.variants.every((v) => v.available === 0)}>
              Añadir al carrito
            </button>
          </form>
          <p className="muted" style={{ marginTop: "1.5rem", fontSize: ".9rem" }}>
            Entrega en {s.deliveryDays} días hábiles. Envío {formatCop(s.shippingFee)}; gratis desde la {free}.ª prenda.
          </p>
        </div>
      </div>
    </div>
  );
}
