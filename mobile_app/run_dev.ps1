# Auto-detects this machine's LAN IPv4 and runs the Flutter app pointing
# its API_BASE_URL at the local backend. Avoids hard-coding a router IP.
#
# Usage:   .\run_dev.ps1
# Override port:   .\run_dev.ps1 -Port 8001

param(
    [int]$Port = 8000
)

function Get-LocalIPv4 {
    # Prefer an "Up" Wi-Fi or Ethernet adapter with a non-link-local IPv4 address.
    $candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254.*' -and
            $_.PrefixOrigin -ne 'WellKnown'
        } |
        Sort-Object -Property @{Expression = { ($_.InterfaceAlias -match 'Wi-?Fi|Wireless') }; Descending = $true}

    if ($candidates.Count -gt 0) {
        return $candidates[0].IPAddress
    }
    return $null
}

$ip = Get-LocalIPv4
if (-not $ip) {
    Write-Host "Could not detect a LAN IPv4 address. Connect to a network and retry." -ForegroundColor Red
    exit 1
}

$apiUrl = "http://${ip}:${Port}"
Write-Host "API_BASE_URL = $apiUrl" -ForegroundColor Green

flutter run --dart-define=API_BASE_URL=$apiUrl
