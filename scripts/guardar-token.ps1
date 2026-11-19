# Guarda el token de Cloudflare FUERA del repositorio, sin mostrarlo en pantalla ni pasarlo por el chat.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\guardar-token.ps1
$dir = Join-Path $env:USERPROFILE ".nerova"
$file = Join-Path $dir "cloudflare.env"
New-Item -ItemType Directory -Force $dir | Out-Null

function Leer-Secreto($etiqueta) {
  $s = Read-Host $etiqueta -AsSecureString
  $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
  try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($b) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
}

$token = (Leer-Secreto "Token de API de Cloudflare (no se muestra)").Trim()
$account = (Read-Host "Account ID de Cloudflare (no es secreto)").Trim()
if (-not $token) { Write-Host "Token vacío, no se guardó nada."; exit 1 }

$lineas = @("CLOUDFLARE_API_TOKEN=$token")
if ($account) { $lineas += "CLOUDFLARE_ACCOUNT_ID=$account" }
Set-Content -Path $file -Value $lineas -Encoding ascii

# Solo tu usuario puede leer el archivo.
icacls $file /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
Write-Host "Guardado en $file (permisos solo para tu usuario). Longitud del token: $($token.Length)."
