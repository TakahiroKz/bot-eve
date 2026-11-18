import { beforeEach, describe, expect, it } from "vitest";
import { memoryDb, type Db } from "../src/lib/db";
import { listProducts } from "../src/lib/catalog";
import { computeTotals } from "../src/lib/pricing";
import { confirmPayment, createOrder, normalizeLines, OrderError, setOrderStatus, validateCustomer, type Customer } from "../src/lib/orders";
import { getSettings, safeUrl, saveSettings } from "../src/lib/settings";
import { seedIfEmpty } from "../src/lib/seed";

const PRICING = { shippingFee: 15000, freeShippingMinItems: 2 };
const CUSTOMER: Customer = {
  name: "Ana Pérez", email: "ana@example.com", phone: "3001234567",
  department: "Antioquia", city: "Medellín", address: "Calle 10 # 20-30", notes: "",
};

let db: Db;
beforeEach(async () => {
  db = await memoryDb();
  await seedIfEmpty(db);
});

const variantId = async (slug: string, size: string) =>
  (await db.query<{ id: number }>(
    "SELECT v.id FROM variants v JOIN products p ON p.id = v.product_id WHERE p.slug = $1 AND v.size = $2", [slug, size],
  ))[0].id;

describe("precios", () => {
  it("envío 15.000 con 1 prenda y gratis desde 2", () => {
    expect(computeTotals([{ unitPrice: 500000, qty: 1 }], PRICING)).toMatchObject({ shipping: 15000, total: 515000, freeShipping: false });
    expect(computeTotals([{ unitPrice: 500000, qty: 2 }], PRICING)).toMatchObject({ shipping: 0, total: 1000000, freeShipping: true });
    expect(computeTotals([{ unitPrice: 100, qty: 1 }, { unitPrice: 200, qty: 1 }], PRICING).shipping).toBe(0); // 2 prendas distintas
    expect(computeTotals([], PRICING).total).toBe(0);
  });
});

describe("catálogo sembrado", () => {
  it("6 modelos: 3 hombre y 3 mujer, 2 negros y 1 rojo en cada uno; tallas M/L y S/M", async () => {
    const all = await listProducts({}, db);
    expect(all).toHaveLength(6);
    for (const g of ["hombre", "mujer"] as const) {
      const p = all.filter((x) => x.gender === g);
      expect(p.filter((x) => x.color === "Negro")).toHaveLength(2);
      expect(p.filter((x) => x.color === "Rojo")).toHaveLength(1);
      for (const x of p) expect(x.variants.map((v) => v.size)).toEqual(g === "hombre" ? ["M", "L"] : ["S", "M"]);
    }
    expect(all.every((p) => p.images.length > 0)).toBe(true);
  });
});

describe("pedidos y stock", () => {
  it("usa el precio de la base de datos, calcula envío y reserva stock", async () => {
    const v = await variantId("vertice-hombre", "M");
    const o = await createOrder(db, CUSTOMER, [{ variantId: v, qty: 1 }], PRICING, "simulated");
    expect(o.total).toBe(549000 + 15000);
    const p = (await listProducts({}, db)).find((x) => x.slug === "vertice-hombre")!;
    const m = p.variants.find((x) => x.size === "M")!;
    expect(m.stock).toBe(5);
    expect(m.available).toBe(4); // reservada, aún no descontada
  });

  it("no vende más de lo que hay (la reserva cuenta) y se libera al vencer", async () => {
    const v = await variantId("vertice-hombre", "L");
    await createOrder(db, CUSTOMER, [{ variantId: v, qty: 5 }], PRICING, "simulated");
    await expect(createOrder(db, CUSTOMER, [{ variantId: v, qty: 1 }], PRICING, "simulated")).rejects.toThrow(OrderError);
    await db.query("UPDATE orders SET reserved_until = now() - interval '1 minute'");
    await expect(createOrder(db, CUSTOMER, [{ variantId: v, qty: 1 }], PRICING, "simulated")).resolves.toBeTruthy();
  });

  it("pedidos simultáneos de la última unidad: solo uno gana", async () => {
    const v = await variantId("brasa-hombre", "M");
    await db.query("UPDATE variants SET stock = 1 WHERE id = $1", [v]);
    const results = await Promise.allSettled(
      Array.from({ length: 4 }, () => createOrder(db, CUSTOMER, [{ variantId: v, qty: 1 }], PRICING, "simulated")),
    );
    expect(results.filter((r) => r.status === "fulfilled")).toHaveLength(1);
  });

  it("confirmar el pago descuenta stock una sola vez (idempotente)", async () => {
    const v = await variantId("noctua-mujer", "S");
    const o = await createOrder(db, CUSTOMER, [{ variantId: v, qty: 2 }], PRICING, "simulated");
    expect(o.total).toBe(529000 * 2); // envío gratis
    expect(await confirmPayment(db, o.code, "ref-1")).toBe("paid");
    expect(await confirmPayment(db, o.code, "ref-1")).toBe("already");
    expect((await db.query<{ stock: number }>("SELECT stock FROM variants WHERE id = $1", [v]))[0].stock).toBe(3);
    expect(await confirmPayment(db, "NOEXISTE", "x")).toBe("missing");
  });

  it("pago con reserva vencida y sin stock queda marcado para revisión", async () => {
    const v = await variantId("eclipse-mujer", "M");
    const o = await createOrder(db, CUSTOMER, [{ variantId: v, qty: 2 }], PRICING, "simulated");
    await db.query("UPDATE variants SET stock = 1 WHERE id = $1", [v]);
    await confirmPayment(db, o.code, "ref");
    const [row] = await db.query<{ status: string; notes: string }>("SELECT status, notes FROM orders WHERE code = $1", [o.code]);
    expect(row.status).toBe("paid");
    expect(row.notes).toContain("ALERTA");
    expect((await db.query<{ stock: number }>("SELECT stock FROM variants WHERE id = $1", [v]))[0].stock).toBe(0);
  });

  it("flujo de estados del panel; cancelar un pedido pagado devuelve el stock", async () => {
    const v = await variantId("carmin-mujer", "S");
    const o = await createOrder(db, CUSTOMER, [{ variantId: v, qty: 1 }], PRICING, "simulated");
    await expect(setOrderStatus(db, o.code, "shipped")).rejects.toThrow(OrderError); // pendiente no puede enviarse
    await confirmPayment(db, o.code, "r");
    await setOrderStatus(db, o.code, "shipped");
    await setOrderStatus(db, o.code, "cancelled");
    expect((await db.query<{ stock: number }>("SELECT stock FROM variants WHERE id = $1", [v]))[0].stock).toBe(5);
  });

  it("valida datos del cliente y normaliza líneas", () => {
    expect(validateCustomer(CUSTOMER)).toBeNull();
    expect(validateCustomer({ ...CUSTOMER, email: "malo" })).toMatch(/correo/);
    expect(validateCustomer({ ...CUSTOMER, phone: "abc" })).toMatch(/teléfono/);
    expect(normalizeLines([{ variantId: 1, qty: 2 }, { variantId: 1, qty: 9 }, { variantId: 2, qty: 0 }, { variantId: 3, qty: -1 }]))
      .toEqual([{ variantId: 1, qty: 5 }]);
  });

  it("rechaza carrito vacío y productos inactivos", async () => {
    await expect(createOrder(db, CUSTOMER, [], PRICING, "simulated")).rejects.toThrow(/vacío/);
    const v = await variantId("vertice-hombre", "M");
    await db.query("UPDATE products SET active = false WHERE slug = 'vertice-hombre'");
    await expect(createOrder(db, CUSTOMER, [{ variantId: v, qty: 1 }], PRICING, "simulated")).rejects.toThrow(/disponible/);
  });
});

describe("configuración", () => {
  it("valores por defecto y guardado; los enlaces peligrosos se descartan", async () => {
    const s = await getSettings(db);
    expect(s).toMatchObject({ shippingFee: 15000, freeShippingMinItems: 2, deliveryDays: 3 });
    await saveSettings(db, { shipping_fee: "18000", whatsapp: "+57 300 123 4567", inventado: "x" });
    const t = await getSettings(db);
    expect(t.shippingFee).toBe(18000);
    expect(t.whatsapp).toBe("573001234567");
    expect(safeUrl("javascript:alert(1)")).toBe("");
    expect(safeUrl("https://instagram.com/tienda")).toBe("https://instagram.com/tienda");
  });
});
