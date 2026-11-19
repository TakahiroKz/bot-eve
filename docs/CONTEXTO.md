# Contexto completo del proyecto — Nerova (tienda de chaquetas de cuero)

> Documento de traspaso: permite a una persona o a un agente nuevo retomar el proyecto sin haber visto la conversación.
> Última actualización: 2026-11-19. Rama de trabajo: `claude/eve-hauling-bot-plan-ej6pj5`. **No incluye secretos** (ni tokens ni claves); ver «Gestión de secretos».

## 1. Resumen en 30 segundos
- **Qué es:** tienda online propia de **chaquetas de cuero** para Colombia (COP), con catálogo, inventario por talla, carrito, checkout, pagos, correo de confirmación y panel de administración oculto.
- **Marca:** **Nerova** («Chaquetas de cuero» como subtítulo). Dominio comprado: **`nerova.com.co`** (en Cloudflare Registrar).
- **Dueño:** Leo (persona natural, Colombia). Habla español; prefiere planificar antes de construir y que se verifique con fuentes.
- **Estado:** la tienda funciona completa en local y en el simulador de Cloudflare (24 pruebas automáticas + recorrido de navegador de 13 comprobaciones). **No está publicada.** Faltan: servidor de base de datos (Oracle), Hyperdrive/túnel, publicación en Cloudflare, pasarela de pago real, política de cambios, facturación, fotos reales y precios definitivos.
- **Decisión de despliegue (opción B):** web en **Cloudflare Workers** (OpenNext) + base de datos **Postgres en un servidor Oracle Cloud gratuito (E2 Micro, 1 GB)**, conectados por **Hyperdrive + Cloudflare Tunnel**. Despliegue automático desde GitHub.

## 2. Historia del repositorio
1. El repositorio (`takahirokz/bot-eve`) contenía antes un **bot de trading en Python** (Binance/MT5). Se limpió por completo en el commit `c184549` para empezar la tienda. Todo el trabajo anterior sigue recuperable: `git checkout 529db4c -- .` (última versión del bot). Conclusión de aquella investigación: solo la ruptura de 4h con 9 pares en cripto pasó la validación; scalping, FX y demás se descartaron (detalle en el historial, `docs/SCALPING_RESEARCH.md` y `docs/CAPITAL_500.md` en esos commits).
2. El nombre del repositorio sigue siendo `bot-eve`; el usuario puede renombrarlo en GitHub (Settings → Repository name) y luego `git remote set-url origin <nueva URL>`.
3. Rama local **`spike-cloudflare`** (commit `dfa2840`): prueba de compatibilidad con Cloudflare, **solo local, no subida**. Contiene un interruptor `SPIKE_ALLOW_SIMULATED` que **no debe fusionarse**. Lo útil ya está en la rama principal (commit `8e24232`).

## 3. Decisiones de negocio (aprobadas)
| Tema | Decisión |
|---|---|
| Mercado | Solo Colombia, COP |
| Catálogo inicial | 6 modelos: 3 de hombre (2 negros, 1 rojo) y 3 de mujer (2 negras, 1 roja) |
| Tallas | Hombre M y L; mujer S y M (12 variantes, stock por variante) |
| Producto | Stock listo, entrega en **3 días hábiles** (parametrizable) |
| Envío | Tarifa única **15.000 COP** (provisional, parametrizable); **gratis desde la 2.ª prenda** (2 o más prendas en el pedido) |
| Cobro | PSE, Nequi y tarjetas con pasarela colombiana — **pasarela por definir** (Wompi, Mercado Pago o PayU); verificar si Wompi acepta persona natural |
| Vendedor | Persona natural (facturación por validar con un contador) |
| Administración | Un solo administrador (el dueño); panel en URL secreta del mismo dominio, no indexable |
| Redes y WhatsApp | Botón flotante de WhatsApp y enlaces de redes **parametrizables desde el panel** |
| Fotos | El dueño tiene fotos reales de producto; las imágenes de IA solo para ambiente/campaña. Hoy hay **fotos de prueba de Unsplash** y un marcador rojo |
| Texto | Voz «propuesta 2»: identidad y precisión estilo BMW/Audi. Eslogan: *«Diseñada para quien no necesita explicarse.»* Evitar afirmaciones no demostrables («100% genuino», «hecho a mano», «de por vida») |

## 4. Identidad (decidida)
- **Nombre:** Nerova. Dominio **nerova.com.co** (comprado). Verificar aún: marca en la **SIC, clase 25**, y `@nerova` en Instagram/TikTok.
- **Paleta «Obsidiana»:** fondo `#0b0b0c`, texto hueso `#f2f0ec`, acento rojo `#b3202f` (botones principales), gris `#9a958d`.
- **Tipografía:** **Oswald** (titulares, mayúsculas) + **Inter** (texto), autoalojadas con `next/font/local` (`src/app/fonts/`).
- **Modelos (familia A, noche y metal):** hombre **Ferro** (negro), **Basalto** (negro), **Ascua** (rojo); mujer **Noxa** (negra), **Lumbre** (negra), **Brasa** (roja). Nota: «Lumbre» aparece como nombre de una parka en la tienda colombiana Vélez; decidir si se conserva.
- Propuestas de diseño en `design/*.html` (1 Obsidiana, 2 Cobre, 3 Acero, 4 elegida: Obsidiana + Oswald).

## 5. Arquitectura y stack
- **Next.js 16** (App Router, TypeScript), React 19. Estilos propios en `src/app/globals.css` (sin librerías de UI).
- **Importante (Next 16):** el antiguo `middleware` se llama **`proxy.ts`** y debe estar en **`src/proxy.ts`** (hay carpeta `src/`). `AGENTS.md` (generado por Next) pide leer `node_modules/next/dist/docs/` antes de usar APIs; `params` y `searchParams` son `Promise`, `cookies()`/`headers()` son asíncronas.
- **Base de datos:** Postgres. `src/lib/db.ts` elige: Hyperdrive (Cloudflare) → `DATABASE_URL` (`pg`) → PGlite embebido en `.data/pg` (desarrollo). En Cloudflare cada consulta abre un cliente nuevo y el esquema **no** se crea al arrancar: usar `npm run db:migrate`.
- **Pagos:** interfaz en `src/lib/payments/`. Solo existe el proveedor **simulado** (bloqueado en producción a propósito). Un pedido pasa a «pagado» **solo** vía `confirmPayment`/`confirmPaymentAndNotify` (futuro webhook), nunca desde el navegador.
- **Stock:** al crear el pedido se reserva 15 min (`reserved_until`); se descuenta al confirmar el pago; bloqueo `FOR UPDATE` evita doble venta; si el pago llega con reserva vencida y sin stock, el pedido queda pagado con alerta en notas.
- **Correo:** proveedor intercambiable (`console` dev → `.data/outbox/`, `resend`, `brevo`, `memory` pruebas). Confirmación al cliente (una sola vez) + aviso al dueño; reenvío desde el panel. Detalle y DNS en `docs/CORREO.md`.
- **Panel:** `ADMIN_PATH` (por defecto `/gestion-privada`) reescrito por `src/proxy.ts` a la carpeta interna `src/app/admin-area/` (acceso directo → 404). `X-Robots-Tag: noindex`, sin enlaces desde la tienda, fuera de sitemap y de `robots.txt` (robots.txt **no** debe mencionarlo). Acceso: contraseña (hash scrypt, `npm run admin:hash`) + TOTP opcional + bloqueo tras 5 intentos; cada página y acción llama `requireAdmin()`.

### Estructura
```
src/proxy.ts                  # reescritura del panel + noindex
src/lib/                      # db, schema, seed, catalog, cart, pricing, orders, settings,
                              # auth, admin, email, order-email, notifications, payments/
src/app/(shop)/               # inicio, hombre, mujer, producto, carrito, checkout, pedido, pago simulado, políticas
src/app/admin-area/           # panel (login, resumen, pedidos, productos, inventario, ajustes)
src/components/               # cabecera, pie, botón WhatsApp, tarjeta de producto
tests/                        # store, auth, email (vitest, 24 pruebas)
scripts/                      # admin-hash.mjs, db-migrate.mjs
deploy/oracle/auditar.sh      # auditoría de solo lectura de un servidor
wrangler.jsonc, open-next.config.ts   # Cloudflare
.github/workflows/            # ci.yml (pruebas), deploy.yml (publica en Cloudflare al hacer push a main)
design/                       # propuestas de diseño (HTML autónomos)
docs/                         # CONTEXTO, CORREO, DESPLIEGUE
PLAN.md, PENDIENTES.md, README.md
```

## 6. Comandos
```
npm install && cp .env.example .env.local   # ajustar ADMIN_PASSWORD (solo dev) y ADMIN_PATH
npm run dev                  # http://localhost:3000
npm test                     # 24 pruebas (Postgres embebido en memoria)
npm run typecheck
npm run admin:hash -- "contraseña larga"     # hash scrypt + secreto TOTP nuevo
npm run db:migrate           # esquema + datos iniciales en DATABASE_URL
npm run cf:build / cf:preview                # compilar / simular Cloudflare (necesita Postgres local en 127.0.0.1:5433)
```
Para borrar los datos de desarrollo: eliminar la carpeta `.data` y reiniciar.

## 7. Seguridad (decisiones)
- Precios y stock siempre se validan en el servidor; el carrito (cookie) solo guarda `variantId` y cantidad.
- Todo texto del cliente se **escapa** en el correo HTML. Los enlaces de redes solo admiten `http(s)`.
- Ningún dato de tarjeta pasa por el servidor. Secretos solo en variables de entorno / secretos de Cloudflare / secretos de GitHub, **nunca en el repositorio**.
- Errores de proveedores de correo se registran sin el contenido del mensaje.
- Riesgos conocidos: middleware de Node **experimental** en el adaptador de OpenNext (fijar versión; mantener la prueba del panel); el simulador de pagos debe seguir bloqueado en producción.

## 8. Despliegue y estado de la infraestructura
- **Cloudflare:** cuenta con dominio `nerova.com.co` (Registrar). La cuenta contiene **otro proyecto del dueño que NO se debe tocar**: zona `evemarket-analyzer.online` y túnel `evemarket`. Aún no hay Workers ni Hyperdrive (verificado por API de solo lectura el 2026-11-19).
- **Prueba de compatibilidad (local):** OpenNext 1.20.17 + Next 16.4.6: paquete 1,49 MB comprimido; carrito, checkout, pago simulado, panel oculto y ajustes funcionan en el simulador de Cloudflare con Postgres local. **No medido:** límite de 10 ms de CPU del plan gratuito (probablemente se necesite Workers Paid, 5 USD/mes), túnel real, Hyperdrive real.
- **Oracle Cloud:** cuenta Pay As You Go. Servidor **E2 Micro (AMD, 1 GB)**, región **us-ashburn-1**, **Ubuntu**, con IP pública. El dueño dice tener **dos máquinas** y debe revisar cuál está vacía: usar `deploy/oracle/auditar.sh` (solo lectura) y pegar la salida. SSH aún no verificado. **Desde la sesión en la nube no hay acceso SSH** a ese servidor (las llaves no deben compartirse): el dueño ejecuta los comandos y pega la salida.
- **Plan para Oracle (pendiente):** swap de 2 GB, SSH solo con llave, Postgres solo en `127.0.0.1` ajustado a 1 GB (`shared_buffers` ~64 MB, `max_connections` ~20), `cloudflared` (túnel) hacia Postgres, copia diaria cifrada fuera del servidor **con prueba de restauración**, alerta de presupuesto de 1 USD, monitor de disponibilidad. Cuidado: Oracle puede recuperar instancias gratuitas inactivas (CPU/red < 20 % durante 7 días) y suspender cuentas inactivas 30 días.
- **Despliegue automático:** `.github/workflows/deploy.yml` (push a `main`: prueba, compila, `wrangler deploy`). Requiere secretos de GitHub `CLOUDFLARE_API_TOKEN` y `CLOUDFLARE_ACCOUNT_ID`. Los secretos de la tienda (`SESSION_SECRET`, `ADMIN_PASSWORD_HASH`, `ADMIN_TOTP_SECRET`, `RESEND_API_KEY`) van en Cloudflare con `wrangler secret put`. `wrangler.jsonc` tiene el id de Hyperdrive como marcador `REEMPLAZAR_CON_EL_ID_DE_HYPERDRIVE`.
- **Ojo con la rama:** los flujos de GitHub se disparan con `main`; el trabajo vive en la rama `claude/eve-hauling-bot-plan-ej6pj5`. Hay que fusionar a `main` (decisión del dueño) para que corran.

## 9. Gestión de secretos
- Existe un **token de API de Cloudflare de desarrollo** que el dueño pegó en la conversación y **autorizó a usar** durante el desarrollo; **será revocado** al terminar. Está **fuera del repositorio** y no debe escribirse en ningún archivo, comentario ni commit. Permisos observados: lectura de zonas, Workers, Hyperdrive, túneles y Registrar. El dueño pidió usarlo; la recomendación de seguridad (revocar y usar un token de permisos mínimos o secretos de GitHub) quedó expuesta y él decidió conservarlo temporalmente.
- Claves de Testnet de Binance del proyecto anterior fueron pegadas en una conversación antigua: deben considerarse comprometidas (regenerar).
- Cualquier credencial nueva: preferir el formulario seguro de la plataforma o secretos de GitHub/Cloudflare, no el chat.

## 10. Pendientes (resumen; la lista viva está en `PENDIENTES.md`)
**Decisiones del dueño**
- [ ] Pasarela de pago (consultar a Wompi sobre persona natural; alternativas Mercado Pago/PayU) y su integración + webhook.
- [ ] Política de cambios y devoluciones (Ley 1480), tratamiento de datos (Ley 1581), términos y condiciones (hoy textos provisionales).
- [ ] Facturación como persona natural (contador).
- [ ] Verificar la marca Nerova en la SIC (clase 25) y `@nerova` en redes; decidir si se conserva «Lumbre».
- [ ] Contenido: fotos reales de las 6 prendas, nombres/textos/**precios definitivos** (hoy provisionales: 529.000–599.000), stock real por talla, guía de tallas con medidas reales.

**Técnicos**
- [ ] Servidor Oracle: revisar las dos máquinas, elegir la vacía, preparar scripts (Postgres, túnel, copias, monitoreo).
- [ ] Crear Hyperdrive y túnel, cargar secretos en Cloudflare, ejecutar `db:migrate`, publicar el Worker, asignar `nerova.com.co`.
- [ ] Fusionar a `main` y configurar secretos de GitHub para el despliegue automático.
- [ ] Correo: configurar Cloudflare Email Routing (recibir) + Resend/Brevo (enviar) con el dominio verificado (`docs/CORREO.md`); falta el correo «tu pedido va en camino».
- [ ] Medir el CPU por petición con Workers Paid; vigilar el middleware experimental.
- [ ] Incorporar el recorrido de navegador (Playwright) al repositorio: hoy vive fuera de él (13 comprobaciones: compra, envío gratis, pago, panel, ajustes, WhatsApp/redes, sin enlaces al panel).
- [ ] Copias de seguridad y restauración probada; analítica; SEO final; dominio de correo.
- [ ] Revocar el token de Cloudflare de desarrollo y regenerar claves antiguas expuestas.

## 11. Costos esperados
Correo 0 (Resend 3.000/mes o Brevo ~300/día gratis); dominio `.com.co` ≈ 15 USD/año; Oracle 0 dentro del plan gratuito (alerta de presupuesto); Cloudflare Workers Paid ≈ 5 USD/mes (probable); pasarela de pago: comisión por transacción (por definir). Cifras de terceros: verificar en las páginas oficiales antes de pagar.

## 12. Cómo trabajar con el dueño (acuerdos de estilo)
- Español de Colombia; tono directo. Planificar y obtener aprobación **antes** de construir cosas nuevas; después, avanzar sin pedir permiso para cada paso.
- Verificar con fuentes y decir qué **no** se pudo verificar. No inventar afirmaciones (legales, de producto, de rendimiento).
- Mostrar resultados concretos (capturas, números); explicar conceptos con mecanismos y ejemplos cuando pregunte «qué es».
- Commits solo en la rama designada, con las líneas de atribución; no crear Pull Requests salvo petición. Probar (tipos + pruebas + navegador) antes de subir.
- Nunca guardar secretos en el repositorio; no tocar el proyecto «evemarket» de la misma cuenta de Cloudflare.

## 13. Notas técnicas útiles (trampas ya encontradas)
- `innerText` en las pruebas de navegador devuelve el texto **en mayúsculas** cuando el CSS usa `text-transform: uppercase` (los títulos): usar expresiones insensibles a mayúsculas.
- PGlite no crea la carpeta `.data`: `db.ts` la crea. Si el arranque de la base falla, el siguiente intento reintenta (no se queda con la promesa rota).
- Los archivos de página de Next no pueden exportar utilidades arbitrarias: las constantes compartidas viven en `src/lib/`.
- En producción (`NODE_ENV=production`, también en el Worker) el simulador de pagos y la contraseña en claro del panel están **desactivados**.
