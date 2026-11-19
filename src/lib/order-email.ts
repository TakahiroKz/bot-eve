import { formatCop } from "./pricing";

export interface EmailOrder {
  code: string;
  customer_name: string;
  email: string;
  phone: string;
  department: string;
  city: string;
  address: string;
  notes: string;
  subtotal: number;
  shipping: number;
  total: number;
}
export interface EmailItem {
  product_name: string;
  size: string;
  unit_price: number;
  qty: number;
}
export interface EmailContext {
  storeName: string;
  deliveryDays: number;
  siteUrl: string;
  supportEmail: string;
  whatsapp: string;
}

/** Todo texto que viene del cliente se escapa: el correo es HTML. */
export const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const INK = "#0b0b0c";
const BONE = "#f2f0ec";
const RED = "#b3202f";
const FONT = "Helvetica,Arial,sans-serif";

function shell(ctx: EmailContext, preheader: string, body: string): string {
  return `<!doctype html><html lang="es-CO"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:${INK};font-family:${FONT};color:${INK}">
<span style="display:none;opacity:0;max-height:0;overflow:hidden">${esc(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${INK}"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">
<tr><td style="padding:8px 4px 20px;color:${BONE};font-family:'Arial Narrow',Arial,sans-serif;font-weight:bold;letter-spacing:8px;font-size:18px">${esc(ctx.storeName.toUpperCase())}</td></tr>
<tr><td style="background:${BONE};padding:32px 28px">${body}</td></tr>
<tr><td style="padding:20px 4px;color:#9a958d;font-size:12px;line-height:1.6">${esc(ctx.storeName)} · Chaquetas de cuero. Diseñada para quien no necesita explicarse.</td></tr>
</table></td></tr></table></body></html>`;
}

function itemsTable(items: EmailItem[], o: EmailOrder): string {
  const rows = items
    .map(
      (i) => `<tr><td style="padding:10px 0;border-bottom:1px solid #d8d4cc">${esc(i.product_name)} <span style="color:#6b675f">· talla ${esc(i.size)} × ${i.qty}</span></td>
<td align="right" style="padding:10px 0;border-bottom:1px solid #d8d4cc;white-space:nowrap">${formatCop(i.unit_price * i.qty)}</td></tr>`,
    )
    .join("");
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:15px">${rows}
<tr><td style="padding:10px 0;color:#6b675f">Envío</td><td align="right" style="padding:10px 0">${o.shipping === 0 ? "Gratis" : formatCop(o.shipping)}</td></tr>
<tr><td style="padding:12px 0;font-weight:bold;font-size:17px">Total</td><td align="right" style="padding:12px 0;font-weight:bold;font-size:17px">${formatCop(o.total)}</td></tr></table>`;
}

export function customerConfirmation(o: EmailOrder, items: EmailItem[], ctx: EmailContext) {
  const first = o.customer_name.trim().split(/\s+/)[0];
  const link = `${ctx.siteUrl}/pedido/${encodeURIComponent(o.code)}`;
  const contact = [ctx.supportEmail && esc(ctx.supportEmail), ctx.whatsapp && `WhatsApp +${esc(ctx.whatsapp)}`].filter(Boolean).join(" · ");
  const subject = `Tu pedido ${o.code} está confirmado`;
  const html = shell(
    ctx,
    `Recibimos tu pago. Entrega en ${ctx.deliveryDays} días hábiles.`,
    `<h1 style="margin:0 0 8px;font-family:'Arial Narrow',Arial,sans-serif;font-size:28px;text-transform:uppercase;line-height:1.1">Pedido confirmado</h1>
<p style="margin:0 0 20px;font-size:16px;line-height:1.6">${esc(first)}, recibimos tu pago. Tu pedido <b>${esc(o.code)}</b> ya está en preparación y llegará en <b>${ctx.deliveryDays} días hábiles</b>.</p>
${itemsTable(items, o)}
<p style="margin:24px 0 4px;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#6b675f">Entrega</p>
<p style="margin:0 0 24px;font-size:15px;line-height:1.6">${esc(o.customer_name)}<br>${esc(o.address)}<br>${esc(o.city)}, ${esc(o.department)}<br>${esc(o.phone)}</p>
<a href="${esc(link)}" style="display:inline-block;background:${RED};color:#fff;text-decoration:none;padding:14px 28px;font-size:13px;letter-spacing:3px;text-transform:uppercase">Ver mi pedido</a>
${contact ? `<p style="margin:24px 0 0;font-size:13px;color:#6b675f">¿Dudas? ${contact}</p>` : ""}`,
  );
  const text = [
    `Pedido confirmado · ${o.code}`,
    ``,
    `${first}, recibimos tu pago. Tu pedido llegará en ${ctx.deliveryDays} días hábiles.`,
    ``,
    ...items.map((i) => `- ${i.product_name} (talla ${i.size}) x${i.qty}: ${formatCop(i.unit_price * i.qty)}`),
    `Envío: ${o.shipping === 0 ? "Gratis" : formatCop(o.shipping)}`,
    `Total: ${formatCop(o.total)}`,
    ``,
    `Entrega: ${o.customer_name}, ${o.address}, ${o.city}, ${o.department}. Tel. ${o.phone}`,
    ``,
    `Ver tu pedido: ${link}`,
  ].join("\n");
  return { subject, html, text };
}

export function adminNewOrder(o: EmailOrder, items: EmailItem[], ctx: EmailContext, adminUrl: string) {
  const subject = `Nuevo pedido pagado ${o.code} · ${formatCop(o.total)}`;
  const html = shell(
    ctx,
    subject,
    `<h1 style="margin:0 0 12px;font-family:'Arial Narrow',Arial,sans-serif;font-size:24px;text-transform:uppercase">Nuevo pedido pagado</h1>
<p style="margin:0 0 16px;font-size:15px"><b>${esc(o.code)}</b> · ${esc(o.customer_name)} · ${esc(o.city)}</p>
${itemsTable(items, o)}
<p style="margin:20px 0 4px;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#6b675f">Entrega</p>
<p style="margin:0 0 8px;font-size:15px;line-height:1.6">${esc(o.address)}, ${esc(o.city)}, ${esc(o.department)}<br>${esc(o.phone)} · ${esc(o.email)}</p>
${o.notes ? `<p style="margin:0 0 16px;font-size:14px;color:#6b675f">Notas: ${esc(o.notes)}</p>` : ""}
<a href="${esc(adminUrl)}" style="display:inline-block;background:${INK};color:#fff;text-decoration:none;padding:12px 24px;font-size:13px;letter-spacing:3px;text-transform:uppercase">Abrir en el panel</a>`,
  );
  const text = [
    subject,
    `${o.customer_name} · ${o.address}, ${o.city}, ${o.department} · ${o.phone} · ${o.email}`,
    ...items.map((i) => `- ${i.product_name} (talla ${i.size}) x${i.qty}`),
    o.notes ? `Notas: ${o.notes}` : "",
    `Panel: ${adminUrl}`,
  ]
    .filter(Boolean)
    .join("\n");
  return { subject, html, text };
}
