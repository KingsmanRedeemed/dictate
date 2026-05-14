$ErrorActionPreference = "Stop"

$mutexCreated = $false
$mutex = New-Object System.Threading.Mutex($false, "Local\DictateWatchdog", [ref]$mutexCreated)
if (-not $mutexCreated) {
    return
}

try {
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
    $dictateExe = Join-Path $repoRoot ".venv\Scripts\dictate.exe"
    $logDir = Join-Path $env:LOCALAPPDATA "dictate\logs"
    $watchdogLog = Join-Path $logDir "watchdog.log"
    $daemonArgs = @(
        "--no-tray",
        "--type-backend",
        "pynput",
        "--stt-backend",
        "whisper-cpp",
        "--model",
        "large-v3-turbo-q5_0",
        "--device",
        "auto",
        "--compute-type",
        "int8",
        "--language",
        "en"
    )

    New-Item -ItemType Directory -Force -Path $logDir | Out-Null

    function Write-WatchdogLog {
        param([string]$Message)

        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"
        Add-Content -Path $watchdogLog -Encoding UTF8 -Value "$timestamp $Message"
    }

    function Get-DictateDaemonProcess {
        Get-CimInstance Win32_Process |
            Where-Object {
                $_.CommandLine -like "*$dictateExe*" -and
                $_.CommandLine -like "*--no-tray*"
            }
    }

    function Test-DictateDaemonProfile {
        param($Process)

        $commandLine = $Process.CommandLine
        return (
            $commandLine -like "*--stt-backend whisper-cpp*" -and
            $commandLine -like "*--model large-v3-turbo-q5_0*" -and
            $commandLine -like "*--device auto*" -and
            $commandLine -like "*--compute-type int8*" -and
            $commandLine -like "*--language en*"
        )
    }

    function Stop-WrongProfileDaemons {
        Get-DictateDaemonProcess |
            Where-Object { -not (Test-DictateDaemonProfile $_) } |
            ForEach-Object {
                Write-WatchdogLog "stopping non-turbo Dictate daemon pid=$($_.ProcessId)"
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
    }

    function Start-DictateDaemon {
        if (-not (Test-Path $dictateExe)) {
            Write-WatchdogLog "dictate executable not found: $dictateExe"
            return
        }

        Write-WatchdogLog "starting Dictate daemon"
        Start-Process `
            -FilePath $dictateExe `
            -ArgumentList $daemonArgs `
            -WorkingDirectory $repoRoot `
            -WindowStyle Hidden
    }

    Write-WatchdogLog "watchdog started"

    while ($true) {
        Stop-WrongProfileDaemons
        $runningDaemon = Get-DictateDaemonProcess | Where-Object { Test-DictateDaemonProfile $_ }
        if (-not $runningDaemon) {
            Start-DictateDaemon
        }

        Start-Sleep -Seconds 15
    }
}
finally {
    if ($mutexCreated) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
