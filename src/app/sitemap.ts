import type { MetadataRoute } from "next";
import { listProducts } from "@/lib/catalog";
import { siteUrl } from "@/lib/env";
import { POLICY_SLUGS } from "@/lib/policies";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = siteUrl();
  const products = await listProducts();
  return [
    { url: base, changeFrequency: "weekly", priority: 1 },
    { url: `${base}/hombre`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${base}/mujer`, changeFrequency: "weekly", priority: 0.8 },
    ...POLICY_SLUGS.map((k) => ({ url: `${base}/politicas/${k}`, changeFrequency: "yearly" as const, priority: 0.3 })),
    ...products.map((p) => ({ url: `${base}/producto/${p.slug}`, changeFrequency: "weekly" as const, priority: 0.7 })),
  ];
}
