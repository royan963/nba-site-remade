# NBA History: FastAPI + React in one container.
#     docker build -t nba-history . && docker run -p 8000:8000 nba-history
# The image includes a ready-to-use SQLite database. Set DATABASE_URL to use
# PostgreSQL instead (load it once with `python -m backend.etl.load_db`;
# docker-compose.yml does this for you).

# ---- 1. build the React frontend --------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. API + built frontend ---------------------------------------------------
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY data/ data/
COPY --from=frontend /frontend/dist frontend/dist
RUN python -m backend.etl.load_db

ENV PORT=8000
EXPOSE 8000
# Behind a hosting proxy (Render, etc.) the app needs the real client IP
# (login rate limits are per IP) and scheme (HTTPS-only session cookies) from
# X-Forwarded-* headers. Uvicorn only trusts those from 127.0.0.1 by default,
# and the proxy isn't local, so trust it explicitly. Only do this when the
# container is reachable solely through the proxy, as on Render; otherwise set
# FORWARDED_ALLOW_IPS to the proxy's address.
ENV FORWARDED_ALLOW_IPS="*"
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS}\""]
