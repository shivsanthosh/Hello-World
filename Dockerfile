# ---- build the React interface ----
FROM node:22-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime: FastAPI serves the API and the built interface ----
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PANEL_STUDIO_DATA=/data
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=ui /ui/dist frontend/dist
RUN useradd --create-home studio && mkdir -p /data && chown studio /data
USER studio
VOLUME /data
EXPOSE 8000
WORKDIR /app/backend
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
