<#
.SYNOPSIS
    Switch the LLama-GUI "Custom (User-Provided)" backend between the scoop-managed
    llama.cpp builds (Vulkan / CPU) or a custom fork build, without admin rights.

.DESCRIPTION
    LLama-GUI runs binaries from llama\custom\bin. This script repoints that folder
    (an NTFS junction) at the chosen llama.cpp build. Default everyday backend is
    Vulkan (GPU). Use 'cpu' or 'fork' only for troubleshooting.

    After switching, (re)launch the server from the LLama-GUI "Quick Launch" tab.

.EXAMPLE
    .\switch-llama-backend.ps1 vulkan
    .\switch-llama-backend.ps1 cpu
    .\switch-llama-backend.ps1 fork -ForkPath C:\path\to\fork\build\bin
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('vulkan', 'cpu', 'fork')][string]$Backend,
    [string]$ForkPath = "$env:USERPROFILE\projects\LLama-GUI\llama\forkbin"
)

$ErrorActionPreference = 'Stop'
$customBin = "$env:USERPROFILE\projects\LLama-GUI\llama\custom\bin"

switch ($Backend) {
    'vulkan' { $target = "$env:USERPROFILE\scoop\apps\llama.cpp-vulkan\current" }
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
