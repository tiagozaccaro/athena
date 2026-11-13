<#
.SYNOPSIS
    Athena installer for Windows.

.DESCRIPTION
    irm https://github.com/tiagozaccaro/athena/releases/latest/download/install.ps1 | iex

    With options:
    & ([scriptblock]::Create((irm https://github.com/tiagozaccaro/athena/releases/latest/download/install.ps1))) -Version 0.2.0

    What it does:
      1. Detects a container runtime (Docker Engine in WSL2, Podman, Rancher Desktop).
         Athena doesn't install one on Windows; it prints setup steps when none is found.
      2. Installs uv (https://github.com/astral-sh/uv) if missing.
      3. Installs the Athena server from the GitHub release with `uv tool install`.
      4. Registers Athena to start at logon for the current user.

.PARAMETER Version
    Install a specific version (default: latest release).
.PARAMETER DryRun
    Print what would be done without changing anything.
.PARAMETER Uninstall
    Remove Athena (keeps data unless -Purge is given).
.PARAMETER Purge
    With -Uninstall, also delete Athena's data directory.
.PARAMETER Help
    Show this help.
#>
[Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSAvoidUsingWriteHost', '', Justification = 'Interactive installer output')]
[CmdletBinding()]
param(
    [string]$Version = '',
    [switch]$DryRun,
    [switch]$Uninstall,
    [switch]$Purge,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Repo = 'tiagozaccaro/athena'
$Port = 8420
$InstallRoot = Join-Path $env:LOCALAPPDATA 'Athena\app'
$DataDir = Join-Path $env:LOCALAPPDATA 'Athena\data'
$BinDir = Join-Path $InstallRoot 'bin'

function Write-Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Warn([string]$Message) { Write-Host "warning: $Message" -ForegroundColor Yellow }

# Runs a command, or only prints it with -DryRun.
function Invoke-Step([string]$Display, [scriptblock]$Action) {
    if ($DryRun) {
        Write-Host "  [dry-run] $Display"
    }
    else {
        $global:LASTEXITCODE = 0
        & $Action
        if ($global:LASTEXITCODE -ne 0) { throw "Command failed ($global:LASTEXITCODE): $Display" }
    }
}

function Test-Command([string]$Name) { [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

function Assert-Windows {
    $onWindows = [Environment]::OSVersion.Platform -eq 'Win32NT'
    if (-not $onWindows) { throw 'This installer is for Windows. On Linux or macOS use install.sh.' }
    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($arch -notin @('AMD64', 'ARM64')) { throw "Unsupported architecture: $arch (AMD64 and ARM64 are supported)" }
    Write-Step "Platform: windows/$($arch.ToLower()) ($([Environment]::OSVersion.Version))"
}

function Resolve-AthenaVersion {
    if ($script:Version) { $script:Version = $script:Version.TrimStart('v'); return }
    Write-Step 'Looking up the latest Athena release'
    try {
        $release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest" -Headers @{ 'User-Agent' = 'athena-installer' }
        $script:Version = $release.tag_name.TrimStart('v')
    }
    catch {
        throw "No Athena release found yet at https://github.com/$Repo/releases"
    }
}

# Windows: detect only (see docs/mvp-design.md, decisions log).
function Find-ContainerRuntime {
    $found = @()
    if (Test-Command 'wsl') {
        $null = & wsl.exe -e sh -c 'command -v docker' 2>$null
        if ($LASTEXITCODE -eq 0) { $found += 'Docker Engine in WSL2' }
    }
    if (Test-Command 'podman') { $found += 'Podman' }
    if (Test-Command 'rdctl') { $found += 'Rancher Desktop' }

    if ($found.Count -gt 0) {
        Write-Step "Container runtime found: $($found -join ', ')"
        return
    }
    Write-Warn 'No container runtime found. Athena works without one, but apps and the app store stay hidden until you install one:'
    Write-Host '    Docker Engine in WSL2:  wsl --install, then install docker-ce inside the distro'
    Write-Host '                            https://docs.docker.com/engine/install/ubuntu/'
    Write-Host '    Podman:                 winget install RedHat.Podman, then: podman machine init; podman machine start'
    Write-Host '    Rancher Desktop:        winget install SUSE.RancherDesktop (choose the dockerd engine)'
}

function Install-Uv {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        Write-Step "uv found: $(& $uv.Source --version)"
        $script:Uv = $uv.Source
        return
    }
    Write-Step 'Installing uv'
    $script:Uv = Join-Path $BinDir 'uv.exe'
    Invoke-Step "download https://astral.sh/uv/install.ps1 and run it with UV_INSTALL_DIR=$BinDir" {
        New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
        $installer = Join-Path ([IO.Path]::GetTempPath()) 'uv-install.ps1'
        Invoke-WebRequest 'https://astral.sh/uv/install.ps1' -OutFile $installer -UseBasicParsing
        $env:UV_INSTALL_DIR = $BinDir
        $env:UV_NO_MODIFY_PATH = '1'
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
        Remove-Item $installer -Force
    }
}

# Keeps Athena's Python, tools and entry point in Athena-owned directories.
function Use-UvEnvironment {
    $env:UV_TOOL_DIR = Join-Path $InstallRoot 'tools'
    $env:UV_TOOL_BIN_DIR = $BinDir
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $InstallRoot 'python'
}

function Install-Athena {
    $wheel = "athena_server-$Version-py3-none-any.whl"
    $url = "https://github.com/$Repo/releases/download/v$Version/$wheel"
    $athena = Join-Path $BinDir 'athena.exe'
    Write-Step "Installing Athena $Version"
    Use-UvEnvironment
    Invoke-Step "mkdir $BinDir, $DataDir" {
        New-Item -ItemType Directory -Force -Path $BinDir, $DataDir | Out-Null
    }
    Invoke-Step "uv tool install --force --python 3.13 `"athena-server @ $url`"" {
        & $script:Uv tool install --force --python 3.13 "athena-server @ $url"
    }
    Write-Step 'Registering Athena to start at logon'
    Invoke-Step "athena service install --data-dir `"$DataDir`" --port $Port" {
        & $athena service install --data-dir $DataDir --port $Port
    }
}

function Uninstall-Athena([bool]$PurgeData) {
    Write-Step 'Uninstalling Athena'
    Use-UvEnvironment
    $athena = Join-Path $BinDir 'athena.exe'
    if ($DryRun -or (Test-Path $athena)) {
        Invoke-Step 'athena service uninstall' { & $athena service uninstall }
    }
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    $uvPath = if ($uv) { $uv.Source } else { Join-Path $BinDir 'uv.exe' }
    if ($DryRun -or (Test-Path $uvPath)) {
        Invoke-Step 'uv tool uninstall athena-server' { & $uvPath tool uninstall athena-server }
    }
    Invoke-Step "remove $InstallRoot" { Remove-Item -Recurse -Force $InstallRoot -ErrorAction SilentlyContinue }
    if ($PurgeData) {
        Write-Step "Deleting data in $DataDir"
        Invoke-Step "remove $DataDir" { Remove-Item -Recurse -Force $DataDir -ErrorAction SilentlyContinue }
    }
    else {
        Write-Step "Kept your data in $DataDir (use -Uninstall -Purge to delete it)"
    }
    Write-Step 'Athena was removed.'
}

if ($Help) {
    if ($PSCommandPath) { Get-Help $PSCommandPath -Detailed }
    else { Write-Host 'Options: -Version <x.y.z>  -DryRun  -Uninstall  -Purge  -Help' }
    return
}

Assert-Windows
if ($DryRun) { Write-Step 'Dry run: nothing will be changed' }

if ($Uninstall) {
    Uninstall-Athena -PurgeData $Purge.IsPresent
    return
}

Resolve-AthenaVersion
Find-ContainerRuntime
Install-Uv
Install-Athena

$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
    Select-Object -First 1).IPAddress
if (-not $ip) { $ip = 'localhost' }
if ($DryRun) {
    Write-Step "Dry run finished. Athena $Version would be served at http://${ip}:$Port"
    return
}
Write-Step "Athena $Version is installed."
Write-Host ""
Write-Host "  Open: http://${ip}:$Port"
Write-Host ""
