#!/usr/bin/env bash
# Prepara el servidor para el acceso TEMPORAL mediante un runner de GitHub Actions.
# Léelo antes de ejecutarlo. Hace SOLO esto:
#   1. Crea el usuario "runner" (sin contraseña y sin acceso SSH) con sudo sin contraseña (TEMPORAL).
#   2. Añade 2 GB de swap si no hay (el servidor tiene ~1 GB de RAM).
#   3. Con --quitar-docker: desinstala Docker y containerd (no se usan y consumen memoria).
# Uso:   sudo bash acceso-temporal.sh [--quitar-docker]
# Para deshacerlo: sudo bash revocar-acceso.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo"; exit 1; }

echo "== 1. Usuario runner"
if ! id runner >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" runner
fi
passwd -l runner >/dev/null 2>&1 || true
printf 'runner ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/90-runner-temporal
chmod 440 /etc/sudoers.d/90-runner-temporal
visudo -cf /etc/sudoers.d/90-runner-temporal

echo "== 2. Swap"
if [ -z "$(swapon --show --noheadings)" ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=20 >/dev/null
  echo 'vm.swappiness=20' > /etc/sysctl.d/99-swappiness.conf
else
  echo "ya hay swap:"; swapon --show
fi

if [ "${1:-}" = "--quitar-docker" ]; then
  echo "== 3. Quitar Docker"
  systemctl disable --now docker docker.socket containerd 2>/dev/null || true
  apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  apt-get autoremove -y
fi

echo
free -h | head -3
cat <<'FIN'

Listo. Siguiente paso (con el repositorio ya PRIVADO):
  En GitHub: repositorio -> Settings -> Actions -> Runners -> New self-hosted runner -> Linux, x64.
  Ejecuta los comandos que muestra esa página, PERO como usuario runner (sudo -iu runner) y con estas dos opciones
  extra en el paso "config.sh":   --labels nerova-oracle --unattended --name oracle-e2-micro
  Después, instala el servicio (como administrador):  cd ~runner/actions-runner && sudo ./svc.sh install runner && sudo ./svc.sh start
FIN
