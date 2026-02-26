
# =============================================
#   MENU DNPRA Scraper - Control del Bot
# =============================================

$projectRoot = Split-Path -Parent $PSScriptRoot
$botProcess = $null

function Get-BotPid {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | 
        Where-Object { $_.CommandLine -like "*src\main.py*" -or $_.CommandLine -like "*src/main.py*" } |
        Select-Object -First 1 -ExpandProperty ProcessId
}

function Show-Status {
    $pid = Get-BotPid
    if ($pid) {
        Write-Host "  Estado: " -NoNewline
        Write-Host "CORRIENDO " -ForegroundColor Green -NoNewline
        Write-Host "(PID $pid)"
    } else {
        Write-Host "  Estado: " -NoNewline
        Write-Host "DETENIDO" -ForegroundColor Red
    }
}

function Start-Bot {
    $pid = Get-BotPid
    if ($pid) {
        Write-Host "`n  El bot ya esta corriendo (PID $pid)." -ForegroundColor Yellow
        return
    }
    Write-Host "`n  Iniciando bot..." -ForegroundColor Cyan
    $venv = Join-Path $projectRoot ".venv\Scripts\python.exe"
    $main = Join-Path $projectRoot "src\main.py"
    Start-Process -FilePath $venv -ArgumentList $main -WorkingDirectory $projectRoot -WindowStyle Normal
    Start-Sleep -Seconds 2
    $pid = Get-BotPid
    if ($pid) {
        Write-Host "  Bot iniciado correctamente (PID $pid)." -ForegroundColor Green
    } else {
        Write-Host "  No se pudo confirmar el inicio. Revisa la ventana de Chrome." -ForegroundColor Yellow
    }
}

function Stop-Bot {
    $pid = Get-BotPid
    if (-not $pid) {
        Write-Host "`n  El bot no esta corriendo." -ForegroundColor Yellow
        return
    }
    Write-Host "`n  Deteniendo bot (PID $pid)..." -ForegroundColor Cyan
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    # Matar chromedriver huerfano (NO chrome.exe)
    Get-Process "chromedriver" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    Write-Host "  Bot detenido." -ForegroundColor Green
}

function Show-Logs {
    $logFile = Join-Path $projectRoot "logs\ejecucion_$(Get-Date -Format 'yyyyMMdd').log"
    if (Test-Path $logFile) {
        Write-Host "`n  -- Ultimas 30 lineas del log --" -ForegroundColor Cyan
        Get-Content $logFile -Tail 30
    } else {
        Write-Host "`n  No hay log para hoy todavia." -ForegroundColor Yellow
    }
}

# Loop principal
while ($true) {
    Clear-Host
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "     MENU - DNPRA Scraper Bot" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    Show-Status
    Write-Host ""
    Write-Host "  [1] Iniciar bot"
    Write-Host "  [2] Detener bot"
    Write-Host "  [3] Ver ultimos logs"
    Write-Host "  [4] Salir del menu (el bot sigue corriendo)"
    Write-Host ""
    $choice = Read-Host "  Elegir opcion"
    
    switch ($choice) {
        "1" { Start-Bot; Read-Host "`n  Presiona Enter para continuar" }
        "2" { Stop-Bot; Read-Host "`n  Presiona Enter para continuar" }
        "3" { Show-Logs; Read-Host "`n  Presiona Enter para continuar" }
        "4" { Write-Host "`n  Saliendo del menu. El bot sigue en segundo plano.`n" -ForegroundColor Green; exit }
        default { Write-Host "`n  Opcion invalida." -ForegroundColor Red; Start-Sleep -Seconds 1 }
    }
}
