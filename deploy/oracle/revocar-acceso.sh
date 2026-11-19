#!/usr/bin/env bash
# Deshace el acceso temporal: detiene y desinstala el runner, quita el sudo sin contraseña y (opcional) borra el usuario.
# Uso:   sudo bash revocar-acceso.sh [--borrar-usuario]
# DESPUÉS, en GitHub: Settings -> Actions -> Runners -> elimina "oracle-e2-micro"; y revoca el token de Cloudflare.
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo"; exit 1; }
if [ -x /home/runner/actions-runner/svc.sh ]; then
  (cd /home/runner/actions-runner && ./svc.sh stop; ./svc.sh uninstall) || true
fi
rm -f /etc/sudoers.d/90-runner-temporal
if [ "${1:-}" = "--borrar-usuario" ]; then
  pkill -u runner || true
  deluser --remove-home runner || true
fi
echo "Acceso temporal revocado. Falta: eliminar el runner en GitHub, revocar el token de Cloudflare y rotar la llave SSH."
