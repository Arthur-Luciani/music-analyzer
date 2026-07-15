param(
    [ValidateSet("backend", "frontend", "check", "all")]
    [string]$Target = "all",

    [switch]$InstallDeps,

    [ValidateSet("auto", "cuda", "cpu")]
    [string]$SeparationDevice = "cuda",

    [string]$StorageRoot = "D:\music-analyzer-data"
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendStorageRoot = $StorageRoot
$backendTorchHome = Join-Path $backendStorageRoot "cache\torch"

function Resolve-FfmpegBinaryPath {
    $ffmpegBin = Resolve-FfmpegBin
    if (-not $ffmpegBin) {
        return $null
    }

    $ffmpegExe = Join-Path $ffmpegBin "ffmpeg.exe"
    if (Test-Path $ffmpegExe) {
        return $ffmpegExe
    }

    return $null
}

function Test-CommandAvailable {
    param([string]$CommandName)
    return [bool](Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Resolve-FfmpegBin {
    if (Test-CommandAvailable "ffmpeg") {
        $ffmpegCommand = Get-Command ffmpeg -ErrorAction SilentlyContinue
        if ($ffmpegCommand -and $ffmpegCommand.Source) {
            return Split-Path -Parent $ffmpegCommand.Source
        }
    }

    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path $wingetRoot) {
        $ffmpegExe = Get-ChildItem "$wingetRoot\Gyan.FFmpeg*" -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName
        if ($ffmpegExe) {
            return Split-Path -Parent $ffmpegExe
        }
    }

    return $null
}

function Add-PathPrefix {
    param([string]$PathPrefix)

    if (-not $PathPrefix) {
        return
    }

    $segments = $env:PATH -split ';'
    if ($segments -contains $PathPrefix) {
        return
    }

    $env:PATH = "$PathPrefix;$env:PATH"
}

function Show-LocalRuntimeHints {
    $ffmpegBin = Resolve-FfmpegBin
    $ffmpegBinaryPath = Resolve-FfmpegBinaryPath
    if ($ffmpegBin) {
        Write-Host "FFmpeg detectado em: $ffmpegBin"
        if ($ffmpegBinaryPath) {
            Write-Host "Backend env: FFMPEG_BINARY=$ffmpegBinaryPath"
        }
    }
    else {
        Write-Warning "FFmpeg nao encontrado no PATH. O pipeline local com Demucs pode falhar ao ler audio."
        Write-Host "Instalacao sugerida (Windows): winget install --id Gyan.FFmpeg --source winget"
    }

    Write-Host "Backend env: STORAGE_ROOT=$backendStorageRoot"
    Write-Host "Backend env: TORCH_HOME=$backendTorchHome"
    Write-Host "Backend env: SEPARATION_DEVICE=$SeparationDevice"
}

function Start-Backend {
    Push-Location (Join-Path $projectRoot "backend")
    try {
        if ($InstallDeps) {
            pip install -r requirements.txt -r requirements.pipeline.txt
        }
        $env:STORAGE_ROOT = $backendStorageRoot
        $env:TORCH_HOME = $backendTorchHome
        $env:SEPARATION_DEVICE = $SeparationDevice
        $ffmpegBinaryPath = Resolve-FfmpegBinaryPath
        if ($ffmpegBinaryPath) {
            $env:FFMPEG_BINARY = $ffmpegBinaryPath
        }
        Add-PathPrefix (Resolve-FfmpegBin)
        Show-LocalRuntimeHints
        python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    }
    finally {
        Pop-Location
    }
}

function Start-Frontend {
    Push-Location (Join-Path $projectRoot "frontend")
    try {
        if ($InstallDeps) {
            npm install
        }
        $env:VITE_BACKEND_ORIGIN = "http://localhost:8000"
        npm run dev
    }
    finally {
        Pop-Location
    }
}

function Check-Services {
    $backend = "DOWN"
    $frontend = "DOWN"

    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
            $backend = "UP ($($r.StatusCode))"
        }
    }
    catch {
        $backend = "DOWN ($($_.Exception.Message))"
    }

    try {
        $r2 = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 3
        if ($r2.StatusCode -ge 200 -and $r2.StatusCode -lt 500) {
            $frontend = "UP ($($r2.StatusCode))"
        }
    }
    catch {
        $frontend = "DOWN ($($_.Exception.Message))"
    }

    Write-Host "backend:" $backend
    Write-Host "frontend:" $frontend
}

switch ($Target) {
    "backend" {
        Start-Backend
    }
    "frontend" {
        Start-Frontend
    }
    "check" {
        Check-Services
    }
    "all" {
        $ffmpegBin = Resolve-FfmpegBin
        $ffmpegBinaryPath = Resolve-FfmpegBinaryPath
        Show-LocalRuntimeHints
        $backendCommand = "Push-Location '$projectRoot\backend'; "
        if ($InstallDeps) {
            $backendCommand += "pip install -r requirements.txt -r requirements.pipeline.txt; "
        }
        $backendCommand += "`$env:STORAGE_ROOT='$backendStorageRoot'; `$env:TORCH_HOME='$backendTorchHome'; `$env:SEPARATION_DEVICE='$SeparationDevice';"
        if ($ffmpegBinaryPath) {
            $backendCommand += " `$env:FFMPEG_BINARY='$ffmpegBinaryPath';"
        }
        if ($ffmpegBin) {
            $backendCommand += " `$env:PATH='$ffmpegBin;' + `$env:PATH;"
        }
        $backendCommand += " python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand
        
        $frontendCommand = "Push-Location '$projectRoot\frontend'; "
        if ($InstallDeps) {
            $frontendCommand += "npm install; "
        }
        $frontendCommand += "`$env:VITE_BACKEND_ORIGIN='http://localhost:8000'; npm run dev"
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand
        
        Check-Services
    }
}
