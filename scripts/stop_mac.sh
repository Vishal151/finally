#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="finally-app"

if docker ps -q -f "name=$CONTAINER_NAME" | grep -q .; then
    echo "Stopping $CONTAINER_NAME..."
    docker stop "$CONTAINER_NAME"
fi

docker rm -f "$CONTAINER_NAME" &>/dev/null || true
echo "Container stopped. Data volume preserved."
