import Link from "next/link";
import { ProductCard } from "@/components/ProductCard";
import { listProducts } from "@/lib/catalog";
import { getSettings } from "@/lib/settings";

export default async function Home() {
  const [products, s] = await Promise.all([listProducts(), getSettings()]);
  return (
    <>
      <section className="hero">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/products/prueba-modelo.jpg" alt="Hombre con chaqueta de cuero negra, Nerova (foto de prueba)" />
        <div className="wrap">
          <p className="eyebrow">Chaquetas de cuero · Colección</p>
          <h1>Diseñada para quien no necesita explicarse.</h1>
          <p className="lead">Líneas precisas. Cuero con carácter. Una prenda que dice quién eres antes de que hables.</p>
          <Link href="/hombre" className="btn accent">Hombre</Link>{" "}
          <Link href="/mujer" className="btn ghost">Mujer</Link>
        </div>
      </section>

      <section className="section wrap">
        <div className="values">
          <div>
            <h3>Líneas precisas</h3>
            <p>Cada costura es una decisión. Cada ángulo, una declaración.</p>
          </div>
          <div>
            <h3>Carácter propio</h3>
            <p>No es ropa de temporada. Es la pieza con la que empiezas a vestirte como te ves por dentro.</p>
          </div>
          <div>
            <h3>Lista para ti</h3>
            <p>Stock disponible y entrega en {s.deliveryDays} días hábiles en toda Colombia.</p>
          </div>
        </div>
      </section>

      <section className="section wrap" style={{ paddingTop: 0 }}>
        <p className="eyebrow">La colección</p>
        <h2>Elige la tuya.</h2>
        <div className="grid">{products.map((p) => <ProductCard key={p.id} p={p} />)}</div>
        <p className="muted" style={{ marginTop: "2rem" }}>
          Envío de {new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(s.shippingFee)}.{" "}
          Gratis desde la {s.freeShippingMinItems}.ª prenda.
        </p>
      </section>
    </>
  );
}
