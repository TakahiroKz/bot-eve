# Plan: tienda de chaquetas de cuero

Aprobado. Solo Colombia (COP). Tienda propia: catálogo, inventario, carrito, pagos y panel de administración.

## Catálogo
6 modelos: 3 de hombre (2 negros, 1 rojo) y 3 de mujer (2 negros, 1 rojo). Tallas: hombre M y L, mujer S y M.
Todo en stock listo (12 variantes: modelo × talla, cada una con su stock).

## Reglas de negocio (editables desde el panel)
- Envío: tarifa única provisional de 15.000 COP; gratis con 2 o más prendas en el pedido.
- Entrega: 3 días hábiles.
- Botón flotante de WhatsApp y enlaces de redes sociales parametrizables.

## Arquitectura
- Next.js (App Router, TypeScript). Estilos propios (CSS), sin librerías de UI.
- Postgres: `pg` en producción (Supabase u otro, vía `DATABASE_URL`); PGlite (Postgres embebido) en desarrollo y pruebas.
- Pagos detrás de una interfaz (`src/lib/payments`). Un pedido solo pasa a «pagado» por confirmación del proveedor (webhook), nunca desde el navegador.
  Pasarela real por definir (Wompi, Mercado Pago o PayU); en desarrollo hay un proveedor simulado.
- Stock: reserva de 15 minutos al crear el pedido; se descuenta al confirmar el pago. Sin doble venta de la misma talla.
- Panel de administración: URL propia en el mismo dominio (`ADMIN_PATH`), sin enlaces desde la tienda, `X-Robots-Tag: noindex`,
  fuera del sitemap y de robots.txt. Un solo administrador: contraseña (hash scrypt) + código TOTP opcional, límite de intentos.
- Seguridad: precios y stock siempre validados en el servidor; ningún dato de tarjeta pasa por el servidor; secretos solo en variables de entorno.

## Voz de marca
Propuesta 2 (identidad, estilo BMW/Audi): «Diseñada para quien no necesita explicarse.» Sin afirmaciones no demostrables
(«100% genuino», «hecho a mano», «de por vida»). Español latinoamericano, tono cercano y aspiracional.

## Fases
0. Identidad — hecha: marca **Nerova**, paleta Obsidiana (rojo), tipografía Oswald + Inter, modelos familia A (Ferro, Basalto, Ascua / Noxa, Lumbre, Brasa). Pendiente verificar dominio, marca en la SIC y redes.
1. Cimientos: repositorio, base de datos, modelo de datos.
2. Catálogo: inicio, hombre/mujer, producto, tallas y stock.
3. Carrito y checkout: carrito, datos de envío, envío gratis desde 2 prendas.
4. Pagos: interfaz, proveedor simulado, webhook; pasarela real pendiente.
5. Administración: pedidos, inventario, productos, configuración.
6. Contenido y operación: textos definitivos, correos, SEO, páginas legales.
7. Lanzamiento: dominio, SSL, respaldo, soporte.
Pendientes y decisiones abiertas: ver `PENDIENTES.md`.
