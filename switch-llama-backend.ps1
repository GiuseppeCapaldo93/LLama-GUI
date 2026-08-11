<#
.SYNOPSIS
    Switch the LLama-GUI "Custom (User-Provided)" backend between the scoop-managed
    llama.cpp builds (Vulkan / CPU) or a custom fork build, without admin rights.

.DESCRIPTION
    LLama-GUI runs binaries from llama\custom\bin. This script repoints that folder
    (an NTFS junction) at the chosen llama.cpp build. Default everyday backend is
    Vulkan (GPU). Use 'cpu' or 'fork' only for troubleshooting.

    Backends:
      vulkan - scoop llama.cpp-vulkan. Best token generation (decode) on the 780M.
      rocm   - AMD/Lemonade ROCm build for gfx110X (native gfx1103, self-contained
               HIP runtime). ~10-18% faster prompt processing, ~5-24% slower decode.
               Prefer it for long-context / document ingestion workloads.
      cpu    - scoop llama.cpp-cpu. Troubleshooting only.
      fork   - a locally built tree.

    After switching, (re)launch the server from the LLama-GUI "Quick Launch" tab.

.EXAMPLE
    .\switch-llama-backend.ps1 vulkan
    .\switch-llama-backend.ps1 rocm
    .\switch-llama-backend.ps1 cpu
    .\switch-llama-backend.ps1 fork -ForkPath C:\path\to\fork\build\bin
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('vulkan', 'rocm', 'cpu', 'fork')][string]$Backend,
    [string]$ForkPath = "$env:USERPROFILE\projects\LLama-GUI\llama\forkbin"
)

$ErrorActionPreference = 'Stop'
$customBin = "$env:USERPROFILE\projects\LLama-GUI\llama\custom\bin"

switch ($Backend) {
    'vulkan' { $target = "$env:USERPROFILE\scoop\apps\llama.cpp-vulkan\current" }
    'rocm'   { $target = "$env:USERPROFILE\projects\llama-rocm-gfx110X" }
    'cpu'    { $target = "$env:USERPROFILE\scoop\apps\llama.cpp-cpu\current" }
    'fork'   { $target = $ForkPath }
}

if (-not (Test-Path $target)) { throw "Backend target not found: $target" }
if (-not (Test-Path (Join-Path $target 'llama-server.exe'))) {
    throw "llama-server.exe not found in $target"
}

# Safely remove the existing junction (rmdir removes the reparse point, not the target).
if (Test-Path $customBin) {
    cmd /c rmdir "$customBin" 2>$null
    if (Test-Path $customBin) { Remove-Item $customBin -Recurse -Force }
}

New-Item -ItemType Junction -Path $customBin -Target $target | Out-Null
Write-Host "Switched LLama-GUI custom backend -> $Backend" -ForegroundColor Green
Write-Host "  $customBin  ->  $target"
& (Join-Path $customBin 'llama-server.exe') --list-devices
Write-Host "Now (re)launch the server from the LLama-GUI 'Quick Launch' tab." -ForegroundColor Yellow
