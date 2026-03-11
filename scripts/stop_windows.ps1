$ErrorActionPreference = "Stop"

$ContainerName = "finally-app"

$running = docker ps -q -f "name=$ContainerName" 2>$null
if ($running) {
    Write-Host "Stopping $ContainerName..."
    docker stop $ContainerName
}

docker rm -f $ContainerName 2>$null
Write-Host "Container stopped. Data volume preserved."
