# syntax=docker/dockerfile:1

FROM node:26-alpine AS web-build
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.11-slim AS relay
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COMMONS_HOME=/data/.commons \
    COMMONS_RELAY_DB=/data/relay.db
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY commons/ ./commons/
RUN pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 commons \
    && install -d -o commons -g commons -m 700 /data
USER commons
EXPOSE 8766
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/health', timeout=2)"]
CMD ["commons", "relay", "serve", "--host", "0.0.0.0", "--port", "8766", "--db", "/data/relay.db"]

FROM caddy:2-alpine AS console
COPY deploy/Caddyfile.docker /etc/caddy/Caddyfile
COPY --from=web-build /src/web/dist /srv/commons
EXPOSE 8080
