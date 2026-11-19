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

## Estado al cierre de la sesión en la nube (2026-11-19)
- [x] Servidor Oracle `Instance-00-EveMarketAnalyzer` auditado: limpio, el dueño confirmó que nada depende de él.
- [x] Dominio `nerova.com.co` comprado (Cloudflare).
- [ ] Siguiente: instalar Postgres + túnel en ese servidor, Hyperdrive, publicar. **Detalle completo y arranque en Claude Code local: `docs/CONTEXTO.md` (secciones 8, 10 y 14).**
- [ ] Rotar la llave SSH (`oracle_vm.key` quedó expuesta en una conversación) y revocar el token de Cloudflare al terminar.
- [ ] Revisar Billing → Cost Analysis de Oracle (las dos A1 de EveMarket podrían exceder el plan gratuito).

## Estado al 2026-11-19 (noche)
- [x] **Publicado:** https://nerova.com.co (Cloudflare Workers + Hyperdrive + túnel a Postgres en Oracle). Panel en una ruta secreta aleatoria (secreto `ADMIN_PATH`).
- [x] **Auditoría de seguridad** y parches: ver `docs/SEGURIDAD.md`.
- [x] **Políticas redactadas** (términos, cambios y devoluciones, envíos, datos personales) en `src/lib/policies.ts`, con el correo `contacto@nerova.com.co`. **Falta revisión de un abogado** y que completes en el panel (Ajustes → Datos legales del vendedor): nombre completo, documento, dirección y ciudad del titular.
- [ ] **Correo `contacto@nerova.com.co`:** Email Routing habilitado; falta que verifiques tu Gmail (correo de Cloudflare) y ejecutes `bash scripts/crear-regla-correo.sh`. Es solo para recibir; para enviar desde esa dirección hace falta Resend/Brevo o «Enviar como» en Gmail.
- [ ] **Bloqueante para vender:** pasarela de pago real + webhook. Con `PAYMENTS_PROVIDER=simulated` el checkout falla en producción a propósito.
- [ ] `EMAIL_PROVIDER` sigue en `memory` (no se envían correos de pedido) hasta configurar Resend o Brevo.
- [ ] Copias de seguridad cifradas de Postgres con restauración probada.
- [ ] Decidir la rama `main` para los flujos de GitHub (`ci.yml`, `deploy.yml`); hoy se despliega a mano desde WSL (OpenNext no compila en Windows).
- [ ] Rotar la llave SSH y revocar el token de Cloudflare cuando el dueño lo autorice.
