import Link from "next/link";
import type { Product } from "@/lib/catalog";
import { formatCop } from "@/lib/pricing";

export function ProductCard({ p }: { p: Product }) {
  const soldOut = p.variants.every((v) => v.available === 0);
  return (
    <Link href={`/producto/${p.slug}`} className="card">
      <div className="ph">
        {p.images[0] && /* eslint-disable-next-line @next/next/no-img-element */ <img src={p.images[0].url} alt={p.images[0].alt} loading="lazy" />}
      </div>
      <div className="meta">
        <div>
          <div className="name">{p.name}</div>
          <div className="sub">{p.color} · {p.gender === "hombre" ? "Hombre" : "Mujer"}</div>
        </div>
        <div>{soldOut ? <span className="tag out">Agotada</span> : formatCop(p.price)}</div>
      </div>
    </Link>
  );
}
