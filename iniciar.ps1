# Inicia tudo o que o DivergentIA precisa: Ollama (se preciso), servidor e navegador.
# Uso: de dois cliques em iniciar.bat (ou rode este arquivo no PowerShell).
# Obs.: mensagens sem acento de proposito (o PowerShell 5.1 le arquivos sem BOM como ANSI).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Importante: usar 127.0.0.1 e nao "localhost". No PowerShell 5.1, "localhost" tenta IPv6 primeiro,
# o Ollama so escuta em IPv4 e a checagem estoura o timeout (o script achava que o Ollama estava fora do ar).
function Test-Url($url) {
    try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true } catch { return $false }
}

Write-Host "1/3 Verificando o Ollama (modelo de IA local)..."
if (-not (Test-Url "http://127.0.0.1:11434/api/tags")) {
    Write-Host "    Ollama nao esta rodando. Iniciando..."
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    for ($i = 0; $i -lt 30 -and -not (Test-Url "http://127.0.0.1:11434/api/tags"); $i++) { Start-Sleep -Seconds 1 }
    if (-not (Test-Url "http://127.0.0.1:11434/api/tags")) {
        Write-Host "    Nao consegui iniciar o Ollama. Abra o aplicativo Ollama e tente de novo."
        exit 1
    }
}

Write-Host "2/3 Iniciando o servidor DivergentIA..."
if (Test-Url "http://127.0.0.1:8000/status") {
    Write-Host "    O servidor ja estava rodando."
    Start-Process "http://localhost:8000"
    exit 0
}
$servidor = Start-Process ".\.venv\Scripts\uvicorn.exe" -ArgumentList "app.main:app", "--port", "8000" -NoNewWindow -PassThru
for ($i = 0; $i -lt 90 -and -not (Test-Url "http://127.0.0.1:8000/status"); $i++) {
    if ($servidor.HasExited) { Write-Host "    O servidor encerrou com erro (veja a mensagem acima)."; exit 1 }
    Start-Sleep -Seconds 1
}

Write-Host "3/3 Abrindo o navegador em http://localhost:8000"
Start-Process "http://localhost:8000"
Write-Host ""
Write-Host "Pronto! O modelo de IA esta sendo carregado em segundo plano (a 1a resposta pode levar um pouco mais)."
Write-Host "Para encerrar, feche esta janela ou pressione Ctrl+C."
$servidor.WaitForExit()
