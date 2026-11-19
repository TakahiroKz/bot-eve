import { getDb, type Db } from "./db";

export interface Settings {
  storeName: string;
  shippingFee: number;
  freeShippingMinItems: number;
  deliveryDays: number;
  whatsapp: string; // solo dígitos con indicativo, p. ej. 573001234567
  whatsappMessage: string;
  supportEmail: string;
  legalName: string;
  legalId: string;
  legalAddress: string;
  legalCity: string;
  instagram: string;
  facebook: string;
  tiktok: string;
  youtube: string;
  x: string;
}

export const DEFAULT_SETTINGS: Record<string, string> = {
  store_name: "Nerova",
  shipping_fee: "15000",
  free_shipping_min_items: "2",
  delivery_days: "3",
  whatsapp: "",
  whatsapp_message: "Hola, quiero información sobre las chaquetas.",
  support_email: "contacto@nerova.com.co",
  legal_name: "",
  legal_id: "",
  legal_address: "",
  legal_city: "",
  instagram: "",
  facebook: "",
  tiktok: "",
  youtube: "",
  x: "",
};

const int = (v: string | undefined, d: number) => {
  const n = Number.parseInt(v ?? "", 10);
  return Number.isFinite(n) && n >= 0 ? n : d;
};

export async function getSettings(db?: Db): Promise<Settings> {
  const d = db ?? (await getDb());
  const rows = await d.query<{ key: string; value: string }>("SELECT key, value FROM settings");
  const m = { ...DEFAULT_SETTINGS, ...Object.fromEntries(rows.map((r) => [r.key, r.value])) };
  return {
    storeName: m.store_name,
    shippingFee: int(m.shipping_fee, 15000),
    freeShippingMinItems: Math.max(1, int(m.free_shipping_min_items, 2)),
    deliveryDays: Math.max(1, int(m.delivery_days, 3)),
    whatsapp: m.whatsapp.replace(/\D/g, ""),
    whatsappMessage: m.whatsapp_message,
    supportEmail: m.support_email.trim() || "contacto@nerova.com.co",
    legalName: m.legal_name,
    legalId: m.legal_id,
    legalAddress: m.legal_address,
    legalCity: m.legal_city,
    instagram: m.instagram,
    facebook: m.facebook,
    tiktok: m.tiktok,
    youtube: m.youtube,
    x: m.x,
  };
}

export async function saveSettings(db: Db, values: Record<string, string>): Promise<void> {
  for (const [key, value] of Object.entries(values)) {
    if (!(key in DEFAULT_SETTINGS)) continue;
    await db.query(
      "INSERT INTO settings(key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
      [key, value],
    );
  }
}

/** Solo se aceptan enlaces http(s); evita javascript: y similares en los botones de redes. */
export function safeUrl(u: string): string {
  try {
    const url = new URL(u.trim());
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : "";
  } catch {
    return "";
  }
}
