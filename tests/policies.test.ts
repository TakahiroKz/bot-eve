import { describe, expect, it } from "vitest";
import { getPolicies, POLICY_SLUGS, sellerIdentity } from "../src/lib/policies";
import { DEFAULT_SETTINGS, type Settings } from "../src/lib/settings";

const base: Settings = {
  storeName: "Nerova", shippingFee: 15000, freeShippingMinItems: 2, deliveryDays: 3, whatsapp: "", whatsappMessage: "",
  supportEmail: "contacto@nerova.com.co", legalName: "", legalId: "", legalAddress: "", legalCity: "",
  instagram: "", facebook: "", tiktok: "", youtube: "", x: "",
};

describe("políticas", () => {
  it("existen las cuatro y todas mencionan el correo de contacto", () => {
    const all = getPolicies(base);
    for (const slug of POLICY_SLUGS) {
      expect(all[slug], slug).toBeDefined();
      expect(JSON.stringify(all[slug])).toContain("contacto@nerova.com.co");
    }
  });

  it("usa los valores de Ajustes (días de entrega y tarifa)", () => {
    const envios = JSON.stringify(getPolicies({ ...base, deliveryDays: 5, shippingFee: 20000, freeShippingMinItems: 3 }).envios);
    expect(envios).toContain("5 días hábiles");
    expect(envios).toMatch(/20\.000/);
    expect(envios).toContain("3 o más prendas");
  });

  it("no inventa la identidad del titular: sin datos legales no aparece ningún nombre", () => {
    expect(sellerIdentity(base)).not.toMatch(/identificado\(a\) con/);
    expect(sellerIdentity({ ...base, legalName: "Ana Pérez", legalId: "C.C. 123", legalCity: "Medellín" })).toContain("Ana Pérez, identificado(a) con C.C. 123");
  });

  it("el correo de contacto por defecto es contacto@nerova.com.co", () => {
    expect(DEFAULT_SETTINGS.support_email).toBe("contacto@nerova.com.co");
  });
});
