import type { Metadata } from "next";
import { ProductCard } from "@/components/ProductCard";
import { listProducts } from "@/lib/catalog";

export const metadata: Metadata = { title: "Chaquetas de cuero para hombre" };

export default async function Hombre() {
  const products = await listProducts({ gender: "hombre" });
  return (
    <div className="wrap section" style={{ paddingTop: 0 }}>
      <div className="page-title">
        <p className="eyebrow">Hombre</p>
        <h1 style={{ fontSize: "clamp(2rem,5vw,3.5rem)" }}>Presencia sin esfuerzo.</h1>
        <p className="muted">Tallas M y L.</p>
      </div>
      <div className="grid">{products.map((p) => <ProductCard key={p.id} p={p} />)}</div>
    </div>
  );
}
