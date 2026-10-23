param(
  [string]$Deck = "runs/GASSUM_BASE.DATA",
  [string]$OutputDirectory = "runs/output"
)

$ErrorActionPreference = "Stop"
$flow = Get-Command flow -ErrorAction SilentlyContinue
if (-not $flow) {
  throw "OPM Flow is not installed on this Windows host. Install WSL2 + Ubuntu 24.04 and the official OPM packages, then run this script inside WSL."
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
& $flow.Source $Deck "--output-dir=$OutputDirectory"

