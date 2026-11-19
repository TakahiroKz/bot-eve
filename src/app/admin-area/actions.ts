"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { ADMIN_COOKIE, ADMIN_TTL_MS, adminUrl, requireAdmin } from "@/lib/admin";
import { loginBlocked, loginFailed, loginOk, signSession, verifyPassword, verifyTotp } from "@/lib/auth";
import { getDb } from "@/lib/db";
import { OrderError, setOrderStatus } from "@/lib/orders";
import { safeUrl, saveSettings } from "@/lib/settings";

const str = (f: FormData, k: string, max = 2000) => String(f.get(k) ?? "").trim().slice(0, max);
const intIn = (v: string, min: number, max: number) => {
  const n = Number.parseInt(v, 10);
  return Number.isInteger(n) && n >= min && n <= max ? n : null;
};
const back = (path: string, params: Record<string, string>) =>
  redirect(`${adminUrl(path)}?${new URLSearchParams(params)}`);

export async function loginAction(formData: FormData) {
  const h = await headers();
  const key = (h.get("x-forwarded-for") ?? "local").split(",")[0].trim();
  if (loginBlocked(key) || loginBlocked("global")) back("/login", { error: "Demasiados intentos. Espera unos minutos." });
  const okPw = await verifyPassword(str(formData, "password", 200));
  const secret = process.env.ADMIN_TOTP_SECRET?.trim();
  const okTotp = !secret || verifyTotp(str(formData, "code", 10), secret);
  if (!okPw || !okTotp) {
    loginFailed(key);
    loginFailed("global");
    back("/login", { error: "Credenciales incorrectas." });
  }
  loginOk(key);
  (await cookies()).set(ADMIN_COOKIE, signSession(ADMIN_TTL_MS), {
    httpOnly: true, sameSite: "strict", secure: process.env.NODE_ENV === "production", path: "/", maxAge: ADMIN_TTL_MS / 1000,
  });
  redirect(adminUrl());
}

export async function logoutAction() {
  (await cookies()).delete(ADMIN_COOKIE);
  redirect(adminUrl("/login"));
}

export async function setStatusAction(formData: FormData) {
  await requireAdmin();
  const code = str(formData, "code", 20);
  try {
    await setOrderStatus(await getDb(), code, str(formData, "status", 20));
  } catch (e) {
    if (e instanceof OrderError) back(`/pedidos/${encodeURIComponent(code)}`, { error: e.message });
    throw e;
  }
  back(`/pedidos/${encodeURIComponent(code)}`, { ok: "Estado actualizado." });
}

export async function saveProductAction(formData: FormData) {
  await requireAdmin();
  const id = intIn(str(formData, "id", 10), 1, 1e9);
  const price = intIn(str(formData, "price", 12), 0, 100_000_000);
  const name = str(formData, "name", 120);
  if (!id || price === null || name.length < 2) back("/productos", { error: "Revisa nombre y precio." });
  const db = await getDb();
  const images = str(formData, "images", 4000)
    .split("\n").map((l) => l.trim()).filter(Boolean)
    .filter((u) => u.startsWith("/products/") || safeUrl(u));
  await db.tx(async (q) => {
    await q(
      "UPDATE products SET name=$2, price=$3, tagline=$4, description=$5, active=$6 WHERE id=$1",
      [id, name, price, str(formData, "tagline", 200), str(formData, "description", 1500), formData.get("active") === "on"],
    );
    if (images.length) {
      await q("DELETE FROM product_images WHERE product_id = $1", [id]);
      for (const [i, url] of images.entries()) {
        await q("INSERT INTO product_images (product_id, url, alt, position) VALUES ($1,$2,$3,$4)", [id, url, name, i]);
      }
    }
  });
  back("/productos", { ok: `«${name}» guardado.` });
}

export async function saveStockAction(formData: FormData) {
  await requireAdmin();
  const id = intIn(str(formData, "id", 10), 1, 1e9);
  const stock = intIn(str(formData, "stock", 6), 0, 100_000);
  if (!id || stock === null) back("/inventario", { error: "Stock inválido." });
  await (await getDb()).query("UPDATE variants SET stock = $2 WHERE id = $1", [id, stock]);
  back("/inventario", { ok: "Stock actualizado." });
}

export async function saveSettingsAction(formData: FormData) {
  await requireAdmin();
  const fee = intIn(str(formData, "shipping_fee", 9), 0, 1_000_000);
  const min = intIn(str(formData, "free_shipping_min_items", 3), 1, 50);
  const days = intIn(str(formData, "delivery_days", 3), 1, 60);
  if (fee === null || min === null || days === null) back("/ajustes", { error: "Revisa envío, umbral y días de entrega." });
  const social = (k: string) => {
    const v = str(formData, k, 300);
    return v ? safeUrl(v) : "";
  };
  await saveSettings(await getDb(), {
    store_name: str(formData, "store_name", 80) || "Nerova",
    shipping_fee: String(fee), free_shipping_min_items: String(min), delivery_days: String(days),
    whatsapp: str(formData, "whatsapp", 20).replace(/\D/g, ""),
    whatsapp_message: str(formData, "whatsapp_message", 200),
    support_email: str(formData, "support_email", 120),
    instagram: social("instagram"), facebook: social("facebook"), tiktok: social("tiktok"),
    youtube: social("youtube"), x: social("x"),
  });
  back("/ajustes", { ok: "Ajustes guardados." });
}
