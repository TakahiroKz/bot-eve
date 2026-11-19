# Auditoría de seguridad (2026-11-19)

Alcance: código de la tienda (Next.js), configuración de Cloudflare y servidor de la base de datos. Método: lectura completa del código
(`src/`, 2.100 líneas), revisión de configuración, pruebas automáticas y verificación en producción. No es una prueba de penetración externa.

## Vulnerabilidades encontradas y parchadas
| # | Hallazgo | Riesgo | Parche |
|---|----------|--------|--------|
| 1 | El límite de intentos del login vivía en memoria. En Cloudflare Workers cada petición puede caer en una instancia distinta, así que no limitaba nada. | Alto: fuerza bruta de la contraseña del panel | Contadores en la base (`rate_limits`): 5 fallos por IP y 40 globales cada 15 min. Verificado en producción (el 6.º intento se bloquea). |
| 2 | La IP del cliente se leía de `x-forwarded-for`, que el cliente puede falsificar para saltarse el límite. | Alto | Se usa `cf-connecting-ip` (lo fija Cloudflare). |
| 3 | Checkout sin límite: se podía acaparar el inventario creando pedidos pendientes (cada uno reserva 15 min). | Medio: denegación de venta | Máximo 8 pedidos por IP por hora. |
| 4 | Sin cabeceras de seguridad. | Medio | CSP (sin frames, plugins ni formularios a otros orígenes), HSTS, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP. `Cache-Control: no-store` en carrito, checkout, pedido y pago. |
| 5 | El código TOTP se podía reutilizar dentro de su ventana de 90 s. | Medio | Cada contador se acepta una sola vez (guardado en la base). |
| 6 | La sesión del panel no se podía revocar (token sin estado, 8 h). | Medio | «Época» de sesión: cerrar sesión invalida todos los tokens emitidos. Solo un administrador autenticado puede revocar (un anónimo no puede cerrar la sesión del dueño). |
| 7 | Validación de correo laxa (aceptaba `a@b.com,otro@x.com`) y sin rechazo de saltos de línea en datos del cliente. | Medio: inyección en correos | Regex estricta, longitud máxima y rechazo de caracteres de control. |
| 8 | Un pago podía confirmar un pedido ya cancelado sin dejar rastro. | Bajo | Queda pagado con una ALERTA en las notas para revisar o reembolsar. |
| 9 | El panel usaba una ruta fija pública (`/gestion-privada`, visible en un repositorio público). | Medio | `ADMIN_PATH` es ahora un secreto de Cloudflare con un valor aleatorio. |
| 10 | Datos personales sin autorización expresa en el checkout (Ley 1581). | Cumplimiento | Casilla obligatoria de términos y política de datos. |

## Infraestructura
- **Cloudflare (zona):** HTTPS obligatorio, TLS mínimo 1.2, TLS 1.3 y reescritura automática a HTTPS activados. Modo SSL: full.
- **Servidor de la base:** Postgres escucha solo en localhost; el acceso desde la tienda es por túnel con Cloudflare Access (service token). SSH solo con llave, sin root. Se instaló `fail2ban` para SSH y se aplicó la actualización de kernel pendiente.
- **Docker eliminado** del servidor (no se usaba).

## Revisado y sin hallazgos
Precios y stock validados siempre en servidor; consultas parametrizadas (sin inyección SQL); texto del cliente escapado en el correo HTML; enlaces de redes solo `http(s)`; el simulador de pagos y la contraseña en claro están desactivados en producción; todas las páginas y acciones del panel llaman a `requireAdmin()`; las Server Actions verifican el origen.

## Riesgos aceptados o pendientes
- **`npm audit`:** 3 avisos moderados (`glob`, `minimatch`) en herramientas de compilación de OpenNext, no en el código que corre en producción. La «corrección» automática degrada OpenNext a una versión incompatible; se resolverá al actualizar el adaptador.
- **CSP con `'unsafe-inline'` en scripts:** necesario para que Next.js hidrate la página sin nonces. Mitigado con el resto de directivas.
- **Webhook de pagos:** aún no existe (no hay pasarela real). Cuando se implemente debe verificar la firma del proveedor y ser idempotente (`confirmPayment` ya lo es).
- **DNSSEC** sin activar (recomendado; se activa en el panel de Cloudflare).
- **Rotación de credenciales** (llave SSH y token de Cloudflare): se hará al terminar el despliegue, por indicación del dueño.
- **Copias de seguridad** de la base: pendientes.
