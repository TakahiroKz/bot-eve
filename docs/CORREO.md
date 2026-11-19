# Correo con tu dominio (sin comprar un servicio de correo)

Solo pagas el dominio de la web (`nerova.com.co` o `nerova.co`). El correo se resuelve con tres piezas gratuitas:

| Necesidad | Pieza | Costo |
|---|---|---|
| **Recibir** `hola@tu-dominio` | Cloudflare Email Routing: reenvía a tu Gmail. No envía. Exige que el DNS del dominio esté en Cloudflare. | Gratis |
| **Enviar los correos automáticos** (confirmación de pedido) | Resend (3.000 al mes, 100 al día) o Brevo (~300 al día), con el dominio verificado por SPF y DKIM. | Gratis |
| **Responder desde Gmail** como `hola@tu-dominio` | Gmail «Enviar como» usando el SMTP de Brevo. | Gratis |

Cloudflare también tiene «Email Sending» (beta pública), pero precios y cuotas no están claros; el código admite cambiar de proveedor con una variable de entorno.

## Pasos (cuando compres el dominio)
1. **Confirma con el registrador** que permite cambiar los servidores DNS a Cloudflare (algunos `.com.co` y `.co` lo permiten; compruébalo antes de pagar).
2. Crea una cuenta gratuita en Cloudflare, añade el dominio y cambia los *nameservers* en el registrador.
3. **Recibir:** Cloudflare → Email → Email Routing → crea `hola@` (y `pedidos@` si quieres) hacia tu Gmail.
4. **Enviar:** crea la cuenta en Resend (o Brevo), añade el dominio y pega en Cloudflare DNS los registros que te indique (SPF, DKIM y, en Resend, el MX de retorno). Espera a que figure «Verified».
5. Claves y remitente en las variables de entorno del servidor (nunca en el repositorio):
   ```
   EMAIL_PROVIDER=resend            # o brevo
   RESEND_API_KEY=...               # o BREVO_API_KEY
   EMAIL_FROM=Nerova <pedidos@tu-dominio.com.co>
   EMAIL_REPLY_TO=hola@tu-dominio.com.co
   EMAIL_ADMIN_NOTIFY=tu-gmail@gmail.com   # aviso de cada pedido pagado
   ```
6. Haz un pedido de prueba con la pasarela y confirma que llega al cliente (revisa también «spam»).

## Cuidados
- **Un solo registro SPF por dominio.** Cloudflare Email Routing añade el suyo en el dominio raíz; Resend usa un subdominio de envío y no choca, pero Brevo sí puede: en ese caso hay que fusionar los `include:` en un único SPF.
- Cloudflare Email Routing y un buzón de pago (Zoho, Google Workspace) no pueden compartir los MX del mismo dominio.
- Brevo desactiva una clave SMTP sin uso durante 90 días y puede revisar las cuentas nuevas antes de dejarlas enviar.
- El cuerpo del correo escapa todo texto escrito por el cliente. Los errores del proveedor se registran sin el contenido del mensaje.

## Cómo funciona en el código
- `src/lib/email.ts`: proveedor intercambiable (`console` en desarrollo, `resend`, `brevo`).
- `src/lib/notifications.ts`: `confirmPaymentAndNotify` (lo que deben llamar el webhook de la pasarela y el pago simulado) envía la confirmación al cliente **una sola vez** y el aviso al dueño. Un fallo de correo nunca revierte el pago.
- Panel → pedido: muestra si la confirmación salió y permite reenviarla.
- En desarrollo (`console`) el correo se guarda como HTML en `.data/outbox/` para abrirlo en el navegador.

Fuentes consultadas (verifica las cifras vigentes antes de contratar): [Cloudflare Email Routing/Postmaster](https://developers.cloudflare.com/email-service/reference/postmaster/) · [límites de Cloudflare Email Service](https://developers.cloudflare.com/email-service/platform/limits/) · [plan gratuito de Resend](https://resend.com/blog/new-free-tier) · [Gmail «Enviar como» con Cloudflare](https://sendmailas.com/blog/cloudflare-email-routing-gmail-send-as-guide).
