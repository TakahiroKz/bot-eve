#!/usr/bin/env bash
# Crea la regla de Cloudflare Email Routing: contacto@nerova.com.co -> tu Gmail.
# Requiere que ya hayas hecho clic en el correo de verificación que Cloudflare envió a la dirección de destino.
# Lee el token de ~/.nerova/cloudflare.env (fuera del repositorio).   Uso: bash scripts/crear-regla-correo.sh
set -euo pipefail
set -a; . ~/.nerova/cloudflare.env; set +a
ZONE=b186b4a579cbe3c60a3cedb955c2d872   # zona nerova.com.co
DEST=leonardosp039@gmail.com
curl -s -X POST -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE/email/routing/rules" \
  -d "{\"name\":\"contacto -> Gmail\",\"enabled\":true,\"matchers\":[{\"type\":\"literal\",\"field\":\"to\",\"value\":\"contacto@nerova.com.co\"}],\"actions\":[{\"type\":\"forward\",\"value\":[\"$DEST\"]}]}" \
 | python3 -c "import sys,json;d=json.load(sys.stdin);print('OK: contacto@nerova.com.co reenvía a', '$DEST') if d['success'] else print('Error:', d['errors'])"
