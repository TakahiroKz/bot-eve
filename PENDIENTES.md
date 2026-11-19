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
- [ ] **Dominio:** recomendado comprarlo en **Cloudflare Registrar** (a precio de costo; `.com.co` ≈ 15 USD/año, `.co` ≈ 30 USD/año según su tabla de precios; verifica en pricing.registrar.cloudflare.com). Así el DNS queda en Cloudflare sin trámites, y sirve para Email Routing y la verificación SPF/DKIM.
- [ ] **Alojamiento** de la app (Next.js) por decidir; revisar si el plan gratuito permite uso comercial antes de elegir.
- [ ] **Base de datos en producción:** Supabase gratis alcanza en tamaño (500 MB), pero **pausa el proyecto tras una semana de poca actividad y no incluye copias de seguridad**; para vender de verdad, plan de pago o una copia de seguridad propia.
- [ ] **Costos mensuales esperados:** correo 0 (Resend/Brevo gratis a este volumen), dominio ≈ 1–3 USD/mes, base de datos 0 con riesgo o plan de pago, alojamiento por definir.

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
- [x] Correo de confirmación de pedido: implementado (cliente + aviso al dueño, reenvío desde el panel). Falta **configurarlo con tu dominio**: ver `docs/CORREO.md` (Cloudflare Email Routing para recibir, Resend o Brevo para enviar).
- [ ] Correo «tu pedido va en camino» al marcar como enviado (aún no implementado).
- [ ] Copias de seguridad de la base de datos y analítica.

## Despliegue (decidido: opción B)
- [x] Prueba de compatibilidad con Cloudflare Workers (OpenNext + Hyperdrive): pasa en local. Ver `docs/DESPLIEGUE.md`.
- [ ] Comprar el dominio en Cloudflare Registrar.
- [ ] **Servidor Oracle E2 Micro:** confirmar región, sistema operativo, IP pública y acceso SSH; luego preparar los scripts de instalación (Postgres ajustado a 1 GB, túnel, copias de seguridad). *No tengo acceso a ese servidor desde la sesión en la nube; los comandos los ejecutas tú y me pasas la salida.* El agente de «web-scraping» no estaba alcanzable desde esta sesión.
- [ ] Crear Hyperdrive y túnel, cargar secretos en Cloudflare, configurar `CLOUDFLARE_API_TOKEN`/`CLOUDFLARE_ACCOUNT_ID` en GitHub.
- [ ] Probar CPU por petición con Workers Paid; vigilar actualizaciones del adaptador (middleware de Node experimental).
