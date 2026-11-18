import type { Metadata } from "next";
import { ProductCard } from "@/components/ProductCard";
import { listProducts } from "@/lib/catalog";

export const metadata: Metadata = { title: "Chaquetas de cuero para mujer" };

export default async function Mujer() {
  const products = await listProducts({ gender: "mujer" });
  return (
    <div className="wrap section" style={{ paddingTop: 0 }}>
      <div className="page-title">
        <p className="eyebrow">Mujer</p>
        <h1 style={{ fontSize: "clamp(2rem,5vw,3.5rem)" }}>Menos ruido. Más presencia.</h1>
        <p className="muted">Tallas S y M.</p>
      </div>
      <div className="grid">{products.map((p) => <ProductCard key={p.id} p={p} />)}</div>
    </div>
  );
}
