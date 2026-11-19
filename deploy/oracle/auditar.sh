#!/usr/bin/env bash
# Auditoría de SOLO LECTURA: no instala, no borra, no modifica nada.
# Muestra si el servidor está "limpio". No imprime contraseñas, variables de entorno, historial de comandos ni llaves.
# Uso (dentro del servidor, por SSH):   bash auditar.sh
set -u
sec() { printf '\n===== %s =====\n' "$1"; }

sec "Sistema"
. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
uname -m
uptime -p
echo "Creación aprox. del sistema: $(stat -c %w / 2>/dev/null || echo desconocida)"

sec "Recursos"
free -h | head -2
df -h / | tail -1
nproc

sec "Usuarios con shell (cuentas que pueden entrar)"
awk -F: '$7 ~ /(bash|sh|zsh)$/ {print $1}' /etc/passwd

sec "Últimos accesos"
last -n 8 -a 2>/dev/null | head -10

sec "Servicios en ejecución (nombres)"
systemctl list-units --type=service --state=running --no-legend --no-pager 2>/dev/null | awk '{print $1}'

sec "Puertos escuchando"
ss -tln 2>/dev/null | awk 'NR>1 {print $4}' | sort -u

sec "Docker / contenedores"
if command -v docker >/dev/null 2>&1; then docker ps -a --format '{{.Names}}  {{.Image}}  {{.Status}}' 2>/dev/null || echo "docker instalado, sin permiso para listar (prueba con sudo)"; else echo "docker no instalado"; fi

sec "Bases de datos y servidores web instalados"
for c in postgres psql mysql mysqld mongod redis-server nginx apache2 caddy node python3 java; do
  command -v "$c" >/dev/null 2>&1 && echo "presente: $c"
done

sec "Paquetes instalados manualmente (cantidad y muestra)"
if command -v apt-mark >/dev/null 2>&1; then apt-mark showmanual | wc -l; apt-mark showmanual | head -40; fi

sec "Archivos de usuario (tamaño por carpeta)"
du -sh /home/* /opt/* /srv/* /var/www/* /root 2>/dev/null | sort -h | tail -15

sec "Archivos modificados en los últimos 30 días (home, opt, srv, www)"
find /home /opt /srv /var/www -type f -mtime -30 2>/dev/null | head -25

sec "Tareas programadas"
crontab -l 2>/dev/null || echo "sin crontab del usuario actual"
ls /etc/cron.d 2>/dev/null

sec "Cortafuegos (necesita sudo; si no puedes, ignora)"
sudo -n iptables -S 2>/dev/null | head -20 || echo "sin permiso o no disponible"

printf '\nFin. Revisa el resultado antes de pegarlo: no contiene llaves ni contraseñas, pero sí nombres de usuarios, servicios y rutas.\n'
