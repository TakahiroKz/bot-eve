import type { Db } from "./db";

const PHOTO = "/products/prueba-chaqueta.jpg";
const MODEL = "/products/prueba-modelo.jpg";
const RED = "/products/marcador-rojo.svg";

interface SeedProduct {
  slug: string;
  name: string;
  gender: "hombre" | "mujer";
  color: string;
  tagline: string;
  description: string;
  price: number;
  sizes: string[];
  images: string[];
}

// Nombres, textos y precios PROVISIONALES (ver PENDIENTES.md). Fotos de prueba.
const SEED: SeedProduct[] = [
  {
    slug: "vertice-hombre", name: "Vértice", gender: "hombre", color: "Negro",
    tagline: "Líneas precisas. Presencia sin esfuerzo.",
    description: "Corte biker de silueta limpia. Una prenda que dice quién eres antes de que hables.",
    price: 549000, sizes: ["M", "L"], images: [PHOTO, MODEL],
  },
  {
    slug: "meridiano-hombre", name: "Meridiano", gender: "hombre", color: "Negro",
    tagline: "Sobria por fuera. Inconfundible por dentro.",
    description: "Cada costura es una decisión. Un clásico reinterpretado para quien no sigue la corriente.",
    price: 579000, sizes: ["M", "L"], images: [MODEL, PHOTO],
  },
  {
    slug: "brasa-hombre", name: "Brasa", gender: "hombre", color: "Rojo",
    tagline: "Para quien entra y el lugar lo nota.",
    description: "Color con carácter y una silueta que no pide permiso. Diseñada para destacar sin gritar.",
    price: 599000, sizes: ["M", "L"], images: [RED],
  },
  {
    slug: "noctua-mujer", name: "Noctua", gender: "mujer", color: "Negro",
    tagline: "Hecha para la ciudad cuando se apaga.",
    description: "Silueta moderna y actitud propia. Una pieza que convierte cualquier look en una declaración.",
    price: 529000, sizes: ["S", "M"], images: [PHOTO, MODEL],
  },
  {
    slug: "eclipse-mujer", name: "Eclipse", gender: "mujer", color: "Negro",
    tagline: "Menos ruido. Más presencia.",
    description: "Elegancia contenida, ángulos precisos. El estilo no grita: se nota.",
    price: 559000, sizes: ["S", "M"], images: [MODEL, PHOTO],
  },
  {
    slug: "carmin-mujer", name: "Carmín", gender: "mujer", color: "Rojo",
    tagline: "No sigues la tendencia. La incomodas.",
    description: "Un rojo con intención y un corte que se mueve contigo. Para quien decide cómo se le ve.",
    price: 579000, sizes: ["S", "M"], images: [RED],
  },
];

export async function seedIfEmpty(db: Db): Promise<void> {
  const [{ n }] = await db.query<{ n: number }>("SELECT COUNT(*)::int AS n FROM products");
  if (n > 0) return;
  let pos = 0;
  for (const p of SEED) {
    const [{ id }] = await db.query<{ id: number }>(
      `INSERT INTO products (slug, name, gender, color, tagline, description, price, position)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id`,
      [p.slug, p.name, p.gender, p.color, p.tagline, p.description, p.price, pos++],
    );
    for (const [i, url] of p.images.entries()) {
      await db.query("INSERT INTO product_images (product_id, url, alt, position) VALUES ($1,$2,$3,$4)", [
        id, url, `${p.name}, chaqueta ${p.color.toLowerCase()} (foto de prueba)`, i,
      ]);
    }
    for (const size of p.sizes) {
      await db.query("INSERT INTO variants (product_id, size, stock) VALUES ($1,$2,$3)", [id, size, 5]);
    }
  }
}
