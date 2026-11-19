# Pendientes

## Decisiones del dueño (abiertas)
- [x] **Identidad (fase 0): decidida.** Nombre **Nerova** («Chaquetas de cuero» como subtítulo), paleta Obsidiana (negro `#0b0b0c`, hueso `#f2f0ec`, rojo `#b3202f`), tipografía Oswald (titulares) + Inter (texto). Modelos, familia A: hombre Ferro, Basalto (negros) y Ascua (rojo); mujer Noxa, Lumbre (negras) y Brasa (roja).
- [ ] **Verificar el nombre Nerova** (la búsqueda web no encontró conflictos, pero no reemplaza lo oficial): dominio `nerova.com.co` o `nerova.co` en un registrador; **consulta de marca en la SIC, clase 25** (prendas de vestir); `@nerova` en Instagram y TikTok (o variante limpia).
- [ ] **«Lumbre»** aparece como nombre de una parka de gamuza en Vélez (tienda colombiana). Es solo nombre de modelo, pero decidir si se conserva o se cambia.
- [ ] Verificar en la SIC los nombres de modelo si se quieren proteger.
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
