# Pendientes

## Decisiones del dueño (abiertas)
- [ ] **Nombre de la marca, paleta y tipografía** (fase 0). Hoy el sitio usa «Tienda de chaquetas» y una paleta provisional (`src/app/globals.css`, ajuste «Nombre de la tienda» en el panel).
- [ ] **Pasarela de pago**: consultar a Wompi si acepta persona natural; alternativas Mercado Pago o PayU (PSE, Nequi, tarjetas). Hoy: proveedor simulado.
- [ ] **Facturación** como persona natural: validar con un contador el método (factura electrónica o documento equivalente).
- [ ] **Política de cambios y devoluciones** (derecho de retracto, Ley 1480). Hoy: página con texto provisional.
- [ ] **Política de datos personales** (Ley 1581) y **términos y condiciones**. Hoy: páginas provisionales.
- [ ] **Dominio** y proveedor de alojamiento.

## Contenido
- [ ] Fotos reales de los 6 modelos (hoy: 2 fotos de prueba de Unsplash y marcadores en rojo). Cambiarlas desde `public/products/` y la tabla `product_images` (o desde el panel).
- [ ] Imágenes de modelos con IA (solo ambiente/campaña; la galería del producto usa fotos reales).
- [ ] Nombres, descripciones y **precios definitivos** (hoy provisionales, en `src/lib/seed.ts`).
- [ ] Stock real por talla.
- [ ] Textos definitivos de marca (voz propuesta 2) y de las páginas legales.
- [ ] Guía de tallas con medidas reales.

## Configuración de producción
- [ ] `DATABASE_URL` (Postgres), `ADMIN_PATH` (URL secreta del panel), `ADMIN_PASSWORD_HASH` (`npm run admin:hash`), `ADMIN_TOTP_SECRET`, `SESSION_SECRET`.
- [ ] Tarifa de envío definitiva (hoy 15.000 COP), umbral de envío gratis (2 prendas) y días de entrega (3): editables en el panel.
- [ ] Correo transaccional (confirmación de pedido) — no implementado todavía.
- [ ] Copias de seguridad de la base de datos y analítica.
