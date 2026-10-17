# SPDX-License-Identifier: LGPL-2.1-or-later
# Interactive setup only. It never starts a background service or scheduled task.
[CmdletBinding()]
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

try {
    if (-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) {
        throw 'Use 64-bit PowerShell on 64-bit Windows.'
    }
    if ($env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'This installer supports Windows x64 only.' }
    Set-Location -LiteralPath $PSScriptRoot
    Write-Host 'Oculus CV1 Camera - EXPERIMENTAL' -ForegroundColor Cyan
    Write-Host 'This can and will brick your Sensor.' -ForegroundColor Red
    Write-Host 'Firmware support is limited to the tested revision. Recovery is not guaranteed.'
    Write-Host 'Backups stay PRIVATE under your Local AppData folder. Never upload them.'

    $taskPython = $null
    $taskPythonPrefix = @()
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        foreach ($taskVersion in @('-3.13', '-3.12', '-3.11')) {
            $taskProbe = Start-Process -FilePath (Get-Command py.exe).Source -WindowStyle Hidden -Wait -PassThru -ArgumentList @($taskVersion, '-c', '"import sys,struct;sys.exit(0 if struct.calcsize(chr(80))==8 else 1)"')
            if ($taskProbe.ExitCode -eq 0) {
                $taskPython = (Get-Command py.exe).Source
                $taskPythonPrefix = @($taskVersion)
                break
            }
        }
    }
    if (-not $taskPython -and (Get-Command python.exe -ErrorAction SilentlyContinue)) {
        $taskProbe = Start-Process -FilePath (Get-Command python.exe).Source -WindowStyle Hidden -Wait -PassThru -ArgumentList @('-c', '"import sys,struct;sys.exit(0 if (3,11)<=sys.version_info[:2]<=(3,13) and struct.calcsize(chr(80))==8 else 1)"')
        if ($taskProbe.ExitCode -eq 0) { $taskPython = (Get-Command python.exe).Source }
    }
    if (-not $taskPython) { throw 'Install 64-bit Python 3.11-3.13 from https://www.python.org/downloads/windows/ and run this again.' }
    $taskUsbDk = Join-Path $env:ProgramFiles 'UsbDk Runtime Library\UsbDkHelper.dll'
    if ($CheckOnly) {
        Write-Host ('Python: ready. UsbDk installed: ' + (Test-Path -LiteralPath $taskUsbDk))
        Write-Host 'Check only completed. No downloads, setup, USB access or flash changes.'
        exit 0
    }

    $taskPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $taskPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host 'Requesting administrator access for the USB setup and flash session.'
        $taskShell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $taskProcess = Start-Process -FilePath $taskShell -Verb RunAs -Wait -PassThru -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-NoExit', '-File', ('"' + $PSCommandPath + '"'))
        exit $taskProcess.ExitCode
    }
    $taskData = Join-Path $env:LOCALAPPDATA 'OculusCV1Camera'
    New-Item -ItemType Directory -Path $taskData -Force | Out-Null
    if (-not (Test-Path -LiteralPath $taskUsbDk)) {
        Write-Host 'UsbDk is required only to access USB during flashing/restoration. Webcam use does not need it.'
        Write-Host 'Setup downloads the official Daynix UsbDk 1.0.22 x64 MSI and verifies its SHA256 and signature.'
        if ((Read-Host 'Install UsbDk now? Type YES').Trim() -cne 'YES') { throw 'USB setup cancelled.' }
        $taskMsi = Join-Path $taskData 'UsbDk_1.0.22_x64.msi'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/daynix/UsbDk/releases/download/v1.00-22/UsbDk_1.0.22_x64.msi' -OutFile $taskMsi
        $taskHash = (Get-FileHash -LiteralPath $taskMsi -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($taskHash -ne '91f6f695e1e13c656024e6d3b55620bf08d8835ef05ee0496935ba6bb62466a5') { throw 'UsbDk download checksum mismatch. Nothing will be installed.' }
        if ((Get-AuthenticodeSignature -LiteralPath $taskMsi).Status -ne 'Valid') { throw 'UsbDk signature did not validate. Stop and investigate; do not disable Windows driver security.' }
        $taskInstall = Start-Process -FilePath 'msiexec.exe' -ArgumentList @('/i', ('"' + $taskMsi + '"'), '/passive', '/norestart') -Wait -PassThru
        if ($taskInstall.ExitCode -eq 3010) { throw 'UsbDk requires a reboot. Restart Windows, then run Install.cmd again.' }
        if ($taskInstall.ExitCode -ne 0) { throw ('UsbDk installation failed: ' + $taskInstall.ExitCode) }
        if (-not (Test-Path -LiteralPath $taskUsbDk)) { throw 'UsbDk helper is still missing. Restart Windows before retrying.' }
    }
    $taskVenv = Join-Path $taskData 'python-env-0.1.0'
    if (-not (Test-Path -LiteralPath (Join-Path $taskVenv 'Scripts\python.exe'))) {
        & $taskPython @taskPythonPrefix -m venv $taskVenv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the private Python environment.' }
    }
    $taskRuntime = Join-Path $taskVenv 'Scripts\python.exe'
    & $taskRuntime -m pip --disable-pip-version-check install --only-binary=:all: --require-hashes -r (Join-Path $PSScriptRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. No sensor flash writes were attempted.' }
    & $taskRuntime -m cv1camera
    if ($LASTEXITCODE -ne 0) { throw 'Installer stopped. Keep your backup and read docs/RECOVERY.md if writes had started.' }
}
catch {
    Write-Host ('STOP: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
