# Genera los secretos de la tienda (hash de la contraseña del panel, TOTP, SESSION_SECRET y ruta secreta del panel)
# y los guarda FUERA del repositorio en %USERPROFILE%\.nerova\tienda.env. La contraseña se pide oculta.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\generar-secretos.ps1
$dir = Join-Path $env:USERPROFILE ".nerova"
$file = Join-Path $dir "tienda.env"
New-Item -ItemType Directory -Force $dir | Out-Null

$s = Read-Host "Contraseña del panel (mínimo 12 caracteres, no se muestra)" -AsSecureString
$b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
try { $pw = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
if ($pw.Length -lt 12) { Write-Host "Muy corta (mínimo 12)."; exit 1 }

$salida = node scripts/admin-hash.mjs $pw
$hash = ($salida | Where-Object { $_ -like "ADMIN_PASSWORD_HASH=*" }) -replace "^ADMIN_PASSWORD_HASH=", ""
$totp = (($salida | Where-Object { $_ -like "ADMIN_TOTP_SECRET=*" }) -replace "^ADMIN_TOTP_SECRET=", "") -replace "\s+#.*$", ""

$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$session = [Convert]::ToBase64String($bytes)
$rb = New-Object byte[] 6
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($rb)
$ruta = "/p-" + (($rb | ForEach-Object { $_.ToString("x2") }) -join "")

Set-Content -Path $file -Value @("ADMIN_PASSWORD_HASH=$hash", "ADMIN_TOTP_SECRET=$totp", "SESSION_SECRET=$session", "ADMIN_PATH=$ruta") -Encoding ascii
icacls $file /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null

Write-Host ""
Write-Host "Listo. Guardado en $file"
Write-Host "Anota esto (lo necesitas para entrar al panel):"
Write-Host "  Ruta secreta del panel : $ruta"
Write-Host "  Secreto TOTP (agrégalo a Google Authenticator/Authy como clave manual): $totp"
