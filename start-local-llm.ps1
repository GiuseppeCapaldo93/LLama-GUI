<#
.SYNOPSIS
  Start the scoop llama.cpp (Vulkan) server for hermes / OpenAI-compatible clients
  with a LARGE context window (default 256K) on 127.0.0.1:8080.

  The LLama-GUI UI caps ctx-size at 128K; this script bypasses that so hermes'
  configured context_length (262144) is actually served.

.NOTES
  - Endpoint: http://127.0.0.1:8080/v1  (alias "local-llama" -> matches hermes default model)
  - Flash-attention is ON (required for quantized KV cache).
  - KV cache is quantized (default q8_0) to fit 256K into the 32 GB iGPU.
  - Best 256K fit: LFM2-24B (hybrid arch, small KV). The MoE-attention models
    (Qwen3.6-35B, Nemotron-Omni) have much larger KV; for those use -Ctx 131072
    or -KvType q4_0 if you hit out-of-memory.
  - Runs in the foreground so you can watch load progress. Ctrl+C to stop.
  - Uses port 8080 -> stop any LLama-GUI-launched model first (same port).

.EXAMPLE
  .\start-local-llm.ps1                 # LFM2-24B at 256K
  .\start-local-llm.ps1 -List           # list available models
  .\start-local-llm.ps1 -Model Qwen3.6-35B-A3B-Q4_K_M.gguf -Ctx 131072
  .\start-local-llm.ps1 -KvType q4_0    # smaller KV if you hit OOM at 256K
#>
[CmdletBinding()]
param(
    [string]$Model = "LFM2-24B-A2B-Q4_K_M.gguf",
    [int]$Ctx = 262144,
    [ValidateSet("f16", "q8_0", "q4_0", "q4_1", "q5_0", "q5_1")]
    [string]$KvType = "q8_0",
    [int]$Ngl = 999,
    [string]$ListenHost = "127.0.0.1",
    [int]$Port = 8080,
    [string]$Alias = "local-llama",
    [switch]$List
)

$ErrorActionPreference = "Stop"
$modelsDir = Join-Path $PSScriptRoot "models"

if ($List) {
    Get-ChildItem $modelsDir -Filter *.gguf -File |
        Select-Object Name, @{ n = 'GB'; e = { [math]::Round($_.Length / 1GB, 1) } } |
        Format-Table -AutoSize
    return
}

if (Test-Path -LiteralPath $Model) {
    $modelPath = (Resolve-Path -LiteralPath $Model).Path
} else {
    $modelPath = Join-Path $modelsDir $Model
    if (-not (Test-Path -LiteralPath $modelPath)) {
        throw "Model not found: '$Model'. Run with -List to see available models."
    }
}

# Ensure scoop shims (llama-server = Vulkan build) are on PATH.
$env:PATH = "$env:USERPROFILE\scoop\shims;" +
            [Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('PATH', 'User')
$srv = (Get-Command llama-server -ErrorAction SilentlyContinue).Source
if (-not $srv) { throw "llama-server not found on PATH. Is scoop llama.cpp-vulkan installed and reset?" }

Write-Host "Model    : $modelPath"
Write-Host "Server   : $srv"
Write-Host ("Endpoint : http://{0}:{1}/v1   alias='{2}'" -f $ListenHost, $Port, $Alias)
Write-Host ("Context  : {0} tokens   KV cache: {1}   GPU layers: {2}   flash-attn: on" -f $Ctx, $KvType, $Ngl)
Write-Host "Loading (Ctrl+C to stop)...`n"

& $srv `
    --model $modelPath `
    --alias $Alias `
    --host $ListenHost --port $Port `
    --ctx-size $Ctx `
    --n-gpu-layers $Ngl `
    -fa on `
    --cache-type-k $KvType --cache-type-v $KvType
