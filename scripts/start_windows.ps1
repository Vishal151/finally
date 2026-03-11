$ErrorActionPreference = "Stop"

$ContainerName = "finally-app"
$ImageName = "finally"
$VolumeName = "finally-data"
$Port = 8000
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Build image if --build flag passed or image doesn't exist
$needBuild = $false
if ($args -contains "--build") {
    $needBuild = $true
} else {
    $inspect = docker image inspect $ImageName 2>&1
    if ($LASTEXITCODE -ne 0) { $needBuild = $true }
}

if ($needBuild) {
    Write-Host "Building Docker image..."
    docker build -t $ImageName $ProjectRoot
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

# Check if already running
$running = docker ps -q -f "name=$ContainerName" 2>$null
if ($running) {
    Write-Host "Container already running at http://localhost:$Port"
    exit 0
}

# Remove stopped container
docker rm -f $ContainerName 2>$null

# Run container
docker run -d `
    --name $ContainerName `
    -p "${Port}:8000" `
    -v "${VolumeName}:/app/db" `
    --env-file "$ProjectRoot\.env" `
    $ImageName

if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "FinAlly is running at http://localhost:$Port"
Start-Process "http://localhost:$Port"
