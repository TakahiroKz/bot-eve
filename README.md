# Nerova · Chaquetas de cuero

Tienda propia (Next.js + Postgres) para Colombia: catálogo, inventario por talla, carrito, checkout, pagos y panel de administración.
Plan: [`PLAN.md`](PLAN.md) · Pendientes y decisiones abiertas: [`PENDIENTES.md`](PENDIENTES.md).

## Desarrollo
```bash
npm install
cp .env.example .env.local     # ajusta ADMIN_PASSWORD (solo desarrollo) y ADMIN_PATH
npm run dev                    # http://localhost:3000
npm test                       # pruebas (Postgres embebido en memoria)
npm run typecheck
```
Sin `DATABASE_URL` se usa Postgres embebido (PGlite) en `.data/` con datos de prueba (6 modelos, fotos de prueba, 5 unidades por talla).
Pagos: `PAYMENTS_PROVIDER=simulated` abre una pasarela falsa para probar el flujo; **no funciona en producción** a propósito.

## Panel de administración
Está en la URL secreta `ADMIN_PATH` (por defecto `/gestion-privada`) del mismo dominio: sin enlaces desde la tienda, fuera del sitemap y de
`robots.txt`, con `X-Robots-Tag: noindex`. Acceso con contraseña (y código TOTP si defines `ADMIN_TOTP_SECRET`), con límite de intentos.
En producción genera el hash con `npm run admin:hash -- "tu contraseña larga"` y ponlo en `ADMIN_PASSWORD_HASH`.
Desde el panel: pedidos y estados, productos y precios, inventario, tarifa de envío, envío gratis, días de entrega, WhatsApp y redes sociales.

## Reglas de negocio
- Envío 15.000 COP; gratis con 2 o más prendas (editable).
- Entrega 3 días hábiles (editable).
- Stock reservado 15 minutos al crear el pedido; se descuenta al confirmarse el pago.
- Un pedido solo pasa a «pagado» por confirmación del proveedor de pagos (webhook), nunca por el navegador.
