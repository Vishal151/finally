#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="finally-app"
IMAGE_NAME="finally"
VOLUME_NAME="finally-data"
PORT=8000
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Build image if --build flag passed or image doesn't exist
if [[ "${1:-}" == "--build" ]] || ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "Building Docker image..."
    docker build -t "$IMAGE_NAME" "$PROJECT_ROOT"
fi

# Stop existing container if running
if docker ps -q -f "name=$CONTAINER_NAME" | grep -q .; then
    echo "Container already running at http://localhost:$PORT"
    exit 0
fi

# Remove stopped container with same name
docker rm -f "$CONTAINER_NAME" &>/dev/null || true

# Run container
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$PORT:8000" \
    -v "$VOLUME_NAME:/app/db" \
    --env-file "$PROJECT_ROOT/.env" \
    "$IMAGE_NAME"

echo "FinAlly is running at http://localhost:$PORT"

# Open browser if on macOS
if command -v open &>/dev/null; then
    open "http://localhost:$PORT"
fi
