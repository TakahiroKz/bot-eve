# Despliegue: Cloudflare (web) + Oracle Cloud (base de datos)

```
GitHub (push a main) ──▶ GitHub Actions: prueba, compila y publica ──▶ Cloudflare Workers (la tienda)
                                                                          │  Hyperdrive
                                                                          ▼
                                                  Cloudflare Tunnel ◀── cloudflared ── Oracle E2 Micro: Postgres (solo local)
```
Probado en local (simulador de Cloudflare + Postgres local): ver «Estado de la prueba». **Pendiente de probar:** el túnel y la base real en Oracle.

## Estado de la prueba de compatibilidad
- Compila con OpenNext (paquete 1,49 MB comprimido) y el recorrido completo (carrito, pedido, pago simulado, panel oculto, ajustes) pasa en el simulador de Cloudflare.
- No medible en local: el límite de **10 ms de CPU por petición del plan gratuito** → se espera necesitar Workers Paid (5 USD/mes).
- El middleware de Node (`src/proxy.ts`, protege la ruta secreta del panel) es **experimental** en el adaptador: fijar su versión y conservar la prueba del panel.
- La aplicación ya **no crea tablas al arrancar** en Cloudflare: usa `npm run db:migrate` (una vez, y al cambiar el esquema).

## Pasos
### A. Oracle (servidor E2 Micro, 1 GB) — lo haces tú siguiendo estos pasos; yo preparo los scripts cuando sepamos el sistema operativo
1. Sistema, acceso y cortafuegos: SSH solo con llave, puertos entrantes mínimos (en realidad **ninguno** para la base: el túnel sale hacia Cloudflare), swap de 2 GB, actualizaciones de seguridad automáticas.
2. Postgres solo en `127.0.0.1`, contraseña fuerte, ajustado a 1 GB (`shared_buffers` ~64 MB, `max_connections` ~20).
3. `cloudflared` (túnel) apuntando a `localhost:5432`.
4. Copia de seguridad diaria cifrada fuera del servidor y **prueba de restauración**.
5. Alerta de presupuesto de 1 USD en Oracle y un monitor externo de disponibilidad.

### B. Cloudflare (cuando tengas el dominio)
1. Compra del dominio en Cloudflare Registrar (el DNS queda en Cloudflare).
2. Túnel: Zero Trust → Networks → Tunnels → crear → instalar el conector en el servidor Oracle → ruta privada/hostname hacia Postgres.
3. Hyperdrive: `npx wrangler hyperdrive create nerova-db --connection-string="postgres://USUARIO:CLAVE@HOST:5432/BASE"` y pegar el id que devuelve en `wrangler.jsonc` (`REEMPLAZAR_CON_EL_ID_DE_HYPERDRIVE`).
4. Secretos de la tienda (no van al repositorio): `npx wrangler secret put SESSION_SECRET`, `ADMIN_PASSWORD_HASH` (de `npm run admin:hash`), `ADMIN_TOTP_SECRET`, y las del correo (`RESEND_API_KEY`).
5. Variables no secretas en `wrangler.jsonc`: `ADMIN_PATH`, `SITE_URL`, `EMAIL_PROVIDER`, `EMAIL_FROM`, `PAYMENTS_PROVIDER` (cuando exista el real).
6. Crear el esquema una vez: `DATABASE_URL=... npm run db:migrate`.
7. Despliegue automático: en GitHub → Settings → Secrets → `CLOUDFLARE_API_TOKEN` (permisos «Edit Cloudflare Workers») y `CLOUDFLARE_ACCOUNT_ID`. Cada push a `main` prueba, compila y publica.
8. Dominio de la tienda: Workers → Settings → Domains & Routes → tu dominio.

## Comandos útiles
```
npm run cf:build      # compila para Cloudflare
npm run cf:preview    # simulador local (necesita una base Postgres local; ver wrangler.jsonc)
npm run db:migrate    # crea tablas y datos iniciales en DATABASE_URL
```
