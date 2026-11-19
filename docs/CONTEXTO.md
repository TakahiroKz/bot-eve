> **Actualización 2026-11-19 (noche):** la tienda ya está publicada en https://nerova.com.co. Túnel `nerova-db`, Access, Hyperdrive,
> esquema y secretos creados; Postgres 16 en el servidor Oracle (Docker eliminado, `fail2ban`, kernel actualizado). Auditoría de seguridad
> y parches en `docs/SEGURIDAD.md`; políticas en `src/lib/policies.ts`. Despliegue manual: compilar en WSL (`npx opennextjs-cloudflare build`)
> y `npx wrangler deploy`. Estado vivo y siguientes pasos: `PENDIENTES.md`. Las secciones de abajo describen el estado previo.

# Contexto completo del proyecto — Nerova (tienda de chaquetas de cuero)

> Documento de traspaso: permite a una persona o a un agente nuevo retomar el proyecto sin haber visto la conversación.
> Última actualización: 2026-11-19 (cierre de la sesión en la nube; el trabajo continúa en Claude Code local, ver sección 14). Rama de trabajo: `claude/eve-hauling-bot-plan-ej6pj5`. **No incluye secretos** (ni tokens ni claves); ver «Gestión de secretos».

## 1. Resumen en 30 segundos
- **Qué es:** tienda online propia de **chaquetas de cuero** para Colombia (COP), con catálogo, inventario por talla, carrito, checkout, pagos, correo de confirmación y panel de administración oculto.
- **Marca:** **Nerova** («Chaquetas de cuero» como subtítulo). Dominio comprado: **`nerova.com.co`** (en Cloudflare Registrar).
- **Dueño:** Leo (persona natural, Colombia). Habla español; prefiere planificar antes de construir y que se verifique con fuentes.
- **Estado:** la tienda funciona completa en local y en el simulador de Cloudflare (24 pruebas automáticas + recorrido de navegador de 13 comprobaciones). **No está publicada.** Ya están hechos: código, identidad, correo de confirmación, soporte de Cloudflare, flujos de GitHub, dominio comprado y servidor Oracle auditado (limpio). **Faltan:** instalar Postgres y el túnel en Oracle, Hyperdrive, publicar el Worker, pasarela de pago real, política de cambios, facturación, fotos reales y precios definitivos.
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
- **Cloudflare (verificado por API el 2026-11-19):** dominio **`nerova.com.co`** en Registrar y con zona creada. **No hay Workers ni Hyperdrive todavía.** La cuenta contiene **otro proyecto del dueño que NO se debe tocar**: zona `evemarket-analyzer.online` y túnel `evemarket` (activo; corre en la instancia `EveMarketAnalyzer-02`).
- **Prueba de compatibilidad (local):** OpenNext 1.20.17 + Next 16.4.6: paquete 1,49 MB comprimido; carrito, checkout, pago simulado, panel oculto y ajustes funcionan en el simulador de Cloudflare con Postgres local. **No medido:** límite de 10 ms de CPU del plan gratuito (probablemente se necesite Workers Paid, 5 USD/mes), túnel real, Hyperdrive real.
- **Oracle Cloud (región us-ashburn-1, cuenta Pay As You Go).** Hay 3 instancias:
  | Instancia | Tipo | Uso |
  |---|---|---|
  | `EveMarket-Analyzer` | A1.Flex 2 CPU / 12 GB | Proyecto EveMarket — **no tocar** |
  | `EveMarketAnalyzer-02` | A1.Flex 2 CPU / 12 GB | Proyecto EveMarket; aquí corre el túnel `evemarket` — **no tocar** |
  | **`Instance-00-EveMarketAnalyzer`** (hostname `vnic-evemarketanalyzer`) | **E2.1.Micro, 1 OCPU, 952 MB RAM, disco 48 GB** | **Candidata para la tienda (base de datos). Auditada: limpia.** |
  - **Auditoría (`deploy/oracle/auditar.sh`, 2026-11-19):** Ubuntu 24.04.5, 12 % de disco usado, sin contenedores, bases de datos, servidor web ni cron; solo escucha el puerto 22; `/home/ubuntu` pesa 76 KB; cortafuegos `iptables` solo admite el puerto 22. Restos de un intento anterior: **Docker/containerd y `cloudflared` instalados sin uso** (se pueden quitar; Docker gasta memoria). Cuentas con shell: `root`, `opc`, `ubuntu`. Accesos desde la IP del dueño y desde Cloud Shell (confirmado por el dueño). **El dueño confirmó que nada depende de esa máquina.**
  - **Llave SSH:** el dueño la había perdido, la encontró (`oracle_vm.key`, RSA) y la **subió a la conversación de la sesión en la nube**: debe considerarse expuesta → **rotarla** al terminar (generar par ed25519, añadir la pública a `~ubuntu/.ssh/authorized_keys`, probar, quitar la vieja). Es probable que sea la misma de las instancias de EveMarket.
  - **Posible cargo:** las dos A1 suman 4 CPU/24 GB; la documentación de Oracle habla de un límite gratuito de 2 CPU/12 GB (las fuentes discrepan) → revisar **Billing → Cost Analysis**. No se ha verificado.
  - **Acceso desde la sesión en la nube:** imposible por SSH (el entorno solo sale por un proxy HTTPS y rechaza el puerto 22). Se preparó un canal alternativo (runner de GitHub Actions, ver abajo) que **deja de ser necesario si se trabaja desde Claude Code local**, donde SSH funciona directo.
- **Plan para el servidor (pendiente):** quitar Docker, swap de 2 GB, SSH solo con llave, **Postgres 16 solo en `127.0.0.1`** ajustado a 1 GB (`shared_buffers` ~64 MB, `max_connections` ~20), base y usuario de la tienda con contraseña aleatoria, **`cloudflared`** (túnel nuevo, p. ej. hostname `db.nerova.com.co` → `localhost:5432`; **no reutilizar ni tocar `evemarket`**), copia diaria cifrada fuera del servidor **con prueba de restauración**, alerta de presupuesto de 1 USD, monitor de disponibilidad. Cuidado: Oracle puede recuperar instancias gratuitas inactivas (CPU/red < 20 % durante 7 días) y suspender cuentas inactivas 30 días.
- **Hyperdrive con túnel (por verificar antes de implementar):** según la documentación de Cloudflare, para llegar a una base privada por túnel se usa un hostname TCP del túnel protegido por una aplicación de Cloudflare Access con *service token*, y `wrangler hyperdrive create ... --access-client-id/--access-client-secret`. Confirmar los pasos exactos en la documentación vigente.
- **Canal de acceso temporal (opcional, ya subido):** `.github/workflows/servidor.yml` (ejecuta un comando en el servidor mediante un *runner* propio, etiqueta `nerova-oracle`), `deploy/oracle/acceso-temporal.sh` (crea el usuario `runner` con sudo sin contraseña + swap + opción `--quitar-docker`) y `deploy/oracle/revocar-acceso.sh`. **Requiere repositorio PRIVADO** (un runner propio en un repositorio público permite ejecutar código ajeno en el servidor). **No se instaló ningún runner**; no hace falta si se continúa en Claude Code local.
- **Despliegue automático:** `.github/workflows/deploy.yml` (push a `main`: prueba, compila, `wrangler deploy`) y `ci.yml`. Requieren los secretos de GitHub `CLOUDFLARE_API_TOKEN` y `CLOUDFLARE_ACCOUNT_ID`. Los secretos de la tienda (`SESSION_SECRET`, `ADMIN_PASSWORD_HASH`, `ADMIN_TOTP_SECRET`, `RESEND_API_KEY`) van en Cloudflare con `wrangler secret put`. `wrangler.jsonc` tiene el id de Hyperdrive como marcador `REEMPLAZAR_CON_EL_ID_DE_HYPERDRIVE`.
- **Ojo con la rama:** el repositorio es **público** y su rama por defecto es la de trabajo (`claude/eve-hauling-bot-plan-ej6pj5`); **no existe `main`**, así que `ci.yml` y `deploy.yml` (que escuchan `main`) no corren. Decisión del dueño: crear `main` o cambiar los flujos a la rama actual. Considerar hacer el repositorio privado.

## 9. Gestión de secretos
- **Token de API de Cloudflare de desarrollo:** el dueño lo pegó en la conversación y **autorizó a usarlo** mientras se despliega; **será revocado** al terminar la tienda. **No está en el repositorio** (verificado) y no debe escribirse en ningún archivo, comentario ni commit. Permisos observados: lectura de zonas, Workers, Hyperdrive, túneles y Registrar; ignorar si permite escribir. Account ID: lo conoce el dueño (no se guarda aquí). En local, usarlos como variables de entorno o secretos de GitHub, nunca en archivos versionados.
- **Llave SSH `oracle_vm.key`:** expuesta en la conversación (ver sección 8) → rotar.
- **Claves de Testnet de Binance** del proyecto anterior fueron pegadas en una conversación antigua: regenerar.
- **Otras credenciales por crear:** hash de la contraseña del panel (`npm run admin:hash`), `SESSION_SECRET`, `ADMIN_TOTP_SECRET`, contraseña de Postgres, claves de Resend/Brevo y de la pasarela. Preferir secretos de Cloudflare/GitHub o el formulario seguro de la plataforma, no el chat.

## 10. Pendientes (resumen; la lista viva está en `PENDIENTES.md`)
**Decisiones del dueño**
- [ ] Pasarela de pago (consultar a Wompi sobre persona natural; alternativas Mercado Pago/PayU) y su integración + webhook.
- [ ] Política de cambios y devoluciones (Ley 1480), tratamiento de datos (Ley 1581), términos y condiciones (hoy textos provisionales).
- [ ] Facturación como persona natural (contador).
- [ ] Verificar la marca Nerova en la SIC (clase 25) y `@nerova` en redes; decidir si se conserva «Lumbre».
- [ ] Contenido: fotos reales de las 6 prendas, nombres/textos/**precios definitivos** (hoy provisionales: 529.000–599.000), stock real por talla, guía de tallas con medidas reales.

**Técnicos (orden sugerido)**
1. [ ] **Servidor Oracle** (`Instance-00-EveMarketAnalyzer`): quitar Docker, swap, Postgres 16 ajustado, base/usuario, copias de seguridad cifradas con restauración probada.
2. [ ] **Túnel nuevo** de Cloudflare (no tocar `evemarket`) hacia Postgres + Access/service token; **Hyperdrive**; pegar su id en `wrangler.jsonc`.
3. [ ] Cargar secretos en Cloudflare (`wrangler secret put`), `DATABASE_URL=... npm run db:migrate`, publicar el Worker, asignar `nerova.com.co`; fijar `SITE_URL` y el remitente de correo.
4. [ ] Decidir la rama (`main`) para que corran `ci.yml`/`deploy.yml`; configurar secretos de GitHub; considerar repositorio privado.
5. [ ] Correo: Cloudflare Email Routing (recibir) + Resend/Brevo (enviar) con el dominio verificado (`docs/CORREO.md`); falta el correo «tu pedido va en camino».
6. [ ] Medir el CPU por petición con Workers Paid; vigilar el middleware experimental del adaptador.
7. [ ] Incorporar al repositorio el recorrido de navegador (Playwright, 13 comprobaciones) que hoy vive fuera de él.
8. [ ] Pasarela de pago real + webhook que llame a `confirmPaymentAndNotify`.
9. [ ] Monitoreo de disponibilidad, analítica, SEO final.
10. [ ] **Limpieza de seguridad al terminar:** revocar el token de Cloudflare, rotar la llave SSH, regenerar claves de Binance antiguas, quitar el runner si se instaló, revisar Cost Analysis de Oracle.

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

## 14. Retomar en Claude Code (local) — cronología y arranque
**Qué se hizo en la sesión en la nube (resumen cronológico):** limpieza del proyecto anterior → plan y decisiones de negocio → tienda completa (catálogo, inventario con reservas, carrito, checkout, pagos simulados, panel oculto con auth) → identidad Nerova (4 propuestas de diseño; elegida Obsidiana + Oswald) y modelos familia A → correo de confirmación (cliente + dueño, reenvío desde el panel) → decisión de despliegue B → prueba de compatibilidad con Cloudflare (rama local `spike-cloudflare`, no subida) → soporte de Cloudflare en la rama principal → compra del dominio → auditoría del servidor Oracle → canal de acceso temporal (opcional) → este documento.

**Commits relevantes (rama `claude/eve-hauling-bot-plan-ej6pj5`):** `0b0857c` tienda inicial · `ad5b158` identidad Nerova · `6db6c2a`/`d4dd86a` correo · `8e24232` soporte Cloudflare · `9ee34b1` script de auditoría · `ae8efee` contexto · `d976fcf` canal de acceso temporal.

**Cómo arrancar en tu PC con Claude Code:**
```bash
git clone https://github.com/TakahiroKz/bot-eve && cd bot-eve
git checkout claude/eve-hauling-bot-plan-ej6pj5
npm install
cp .env.example .env.local        # ADMIN_PASSWORD de desarrollo y ADMIN_PATH
npm run dev                        # http://localhost:3000  (panel: /gestion-privada)
npm test && npm run typecheck      # 24 pruebas
```
Pide a Claude Code que lea **`docs/CONTEXTO.md`**, `PLAN.md`, `PENDIENTES.md` y `AGENTS.md` antes de empezar. Ventajas del entorno local: **SSH directo** al servidor Oracle (`ssh -i RUTA ubuntu@IP_DE_LA_CONSOLA`; no hace falta el runner), Playwright y navegador propios, y `wrangler` con sesión local.

**Primer paso recomendado:** SSH a `Instance-00-EveMarketAnalyzer`, ejecutar `bash deploy/oracle/auditar.sh` de nuevo para confirmar el estado y seguir el «Plan para el servidor» de la sección 8. Antes de cualquier acción destructiva o que toque Cloudflare/Oracle, confirmar con el dueño y **no tocar** los recursos de EveMarket.
