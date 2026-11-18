import { getDb, type Db } from "./db";

export interface Variant {
  id: number;
  size: string;
  stock: number;
  available: number; // stock menos reservas vigentes
}
export interface Product {
  id: number;
  slug: string;
  name: string;
  gender: "hombre" | "mujer";
  color: string;
  tagline: string;
  description: string;
  price: number;
  active: boolean;
  images: { url: string; alt: string }[];
  variants: Variant[];
}

type ProductRow = Omit<Product, "images" | "variants">;

export async function expireReservations(db: Db): Promise<void> {
  await db.query("UPDATE orders SET status = 'expired' WHERE status = 'pending' AND reserved_until < now()");
}

export async function listProducts(
  opts: { gender?: "hombre" | "mujer"; includeInactive?: boolean } = {},
  db?: Db,
): Promise<Product[]> {
  const d = db ?? (await getDb());
  await expireReservations(d);
  const where: string[] = [];
  const params: unknown[] = [];
  if (!opts.includeInactive) where.push("active");
  if (opts.gender) {
    params.push(opts.gender);
    where.push(`gender = $${params.length}`);
  }
  const rows = await d.query<ProductRow>(
    `SELECT id, slug, name, gender, color, tagline, description, price, active FROM products
     ${where.length ? "WHERE " + where.join(" AND ") : ""} ORDER BY position, id`,
    params,
  );
  if (!rows.length) return [];
  const ids = rows.map((r) => r.id);
  const images = await d.query<{ product_id: number; url: string; alt: string }>(
    "SELECT product_id, url, alt FROM product_images WHERE product_id = ANY($1::int[]) ORDER BY position, id",
    [ids],
  );
  const variants = await d.query<{ id: number; product_id: number; size: string; stock: number; reserved: number }>(
    `SELECT v.id, v.product_id, v.size, v.stock,
            COALESCE((SELECT SUM(oi.qty) FROM order_items oi JOIN orders o ON o.id = oi.order_id
                      WHERE oi.variant_id = v.id AND o.status = 'pending' AND o.reserved_until >= now()), 0)::int AS reserved
     FROM variants v WHERE v.product_id = ANY($1::int[]) ORDER BY v.id`,
    [ids],
  );
  return rows.map((r) => ({
    ...r,
    images: images.filter((i) => i.product_id === r.id).map((i) => ({ url: i.url, alt: i.alt })),
    variants: variants
      .filter((v) => v.product_id === r.id)
      .map((v) => ({ id: v.id, size: v.size, stock: v.stock, available: Math.max(0, v.stock - v.reserved) })),
  }));
}

export async function getProduct(slug: string, db?: Db): Promise<Product | undefined> {
  const all = await listProducts({}, db);
  return all.find((p) => p.slug === slug);
}
