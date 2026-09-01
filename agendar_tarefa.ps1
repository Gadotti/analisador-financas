<#
.SYNOPSIS
    Registra a análise diária da carteira no Agendador de Tarefas do Windows.

.DESCRIPTION
    Cria uma tarefa que executa scripts/analisar.py de segunda a sexta no
    horário escolhido, gravando a saída em analise.log. Não exige privilégios
    de administrador: a tarefa é criada no contexto do usuário atual.

.EXAMPLE
    .\agendar_tarefa.ps1
    .\agendar_tarefa.ps1 -Horario "18:30" -ComTelegram
    .\agendar_tarefa.ps1 -Remover
#>

param(
    [string]$Horario = "09:00",
    [string]$NomeTarefa = "PortfolioAnalyzer",
    [switch]$ComTelegram,
    [switch]$SemIA,
    [switch]$Remover
)

$ErrorActionPreference = "Stop"
$Base = $PSScriptRoot

if ($Remover) {
    if (Get-ScheduledTask -TaskName $NomeTarefa -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $NomeTarefa -Confirm:$false
        Write-Host "Tarefa '$NomeTarefa' removida." -ForegroundColor Yellow
    } else {
        Write-Host "Tarefa '$NomeTarefa' não existe." -ForegroundColor Yellow
    }
    return
}

# Localiza o Python (PYTHON_BIN tem precedência, para apontar para um venv)
$Python = $env:PYTHON_BIN
if (-not $Python) { $Python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source }
if (-not $Python) { $Python = (Get-Command python.exe  -ErrorAction SilentlyContinue).Source }
if (-not $Python) { throw "Python não encontrado no PATH. Instale o Python 3.10+ e tente novamente." }

$Script = Join-Path $Base "scripts\analisar.py"
if (-not (Test-Path $Script)) { throw "scripts\analisar.py não encontrado em $Base." }

# Monta os argumentos
$Argumentos = @("`"$Script`"")
if ($SemIA)       { $Argumentos += "--sem-ia" }
if ($ComTelegram) { $Argumentos += "--telegram" }
$Log = Join-Path $Base "analise.log"

# Envolve numa chamada do cmd para redirecionar a saída ao log
$Comando = "/c `"`"$Python`" $($Argumentos -join ' ') >> `"$Log`" 2>&1`""

$Acao    = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $Comando -WorkingDirectory $Base
$Gatilho = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $Horario
$Config  = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries `
                                        -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

if (Get-ScheduledTask -TaskName $NomeTarefa -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $NomeTarefa -Confirm:$false
}

Register-ScheduledTask -TaskName $NomeTarefa -Action $Acao -Trigger $Gatilho -Settings $Config `
    -Description "Análise diária da carteira de investimentos" | Out-Null

Write-Host ""
Write-Host "  Tarefa '$NomeTarefa' registrada." -ForegroundColor Green
Write-Host "  Horário .... segunda a sexta, $Horario"
Write-Host "  Análise .... $(if ($SemIA) { 'somente cálculos' } else { 'cálculos + IA' })"
Write-Host "  Telegram ... $(if ($ComTelegram) { 'sim' } else { 'não' })"
Write-Host "  Log ........ $Log"
Write-Host ""
Write-Host "  Testar agora:  Start-ScheduledTask -TaskName $NomeTarefa"
Write-Host "  Remover:       .\agendar_tarefa.ps1 -Remover"
Write-Host ""
