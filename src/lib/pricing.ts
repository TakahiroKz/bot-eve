export interface Totals {
  subtotal: number;
  shipping: number;
  total: number;
  freeShipping: boolean;
  itemCount: number;
}

export interface PricingSettings {
  shippingFee: number;
  freeShippingMinItems: number;
}

/** Subtotal, envío y total en COP (enteros). Envío gratis con `freeShippingMinItems` o más prendas. */
export function computeTotals(
  lines: { unitPrice: number; qty: number }[],
  s: PricingSettings,
): Totals {
  const itemCount = lines.reduce((n, l) => n + l.qty, 0);
  const subtotal = lines.reduce((n, l) => n + l.unitPrice * l.qty, 0);
  const freeShipping = itemCount === 0 || itemCount >= s.freeShippingMinItems;
  const shipping = freeShipping ? 0 : s.shippingFee;
  return { subtotal, shipping, total: subtotal + shipping, freeShipping, itemCount };
}

const cop = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
export const formatCop = (n: number) => cop.format(n);
