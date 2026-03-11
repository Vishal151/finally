# Stage 1: Build frontend static export
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + static files
FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy backend and install dependencies
COPY backend/ ./backend/
RUN cd backend && uv sync --frozen --no-dev

# Copy frontend build output to where the backend expects it
COPY --from=frontend-build /app/frontend/out ./backend/static/

# Create database directory
RUN mkdir -p /app/db

EXPOSE 8000

CMD ["uv", "run", "--directory", "/app/backend", "uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
