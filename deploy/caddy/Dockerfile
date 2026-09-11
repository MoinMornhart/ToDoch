# Web-Container: baut die Oberfläche und liefert sie mit Caddy aus (inkl. HTTPS und /api-Proxy).
# Build-Kontext ist das Repository-Hauptverzeichnis.

FROM node:24-alpine AS build
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /src/build /srv
COPY deploy/caddy/todoch.caddy deploy/caddy/Caddyfile.proxy deploy/caddy/Caddyfile.internal deploy/caddy/Caddyfile.acme /etc/caddy/
COPY deploy/caddy/entrypoint.sh /usr/local/bin/todoch-caddy
RUN chmod 0755 /usr/local/bin/todoch-caddy
EXPOSE 80 443
ENTRYPOINT ["/usr/local/bin/todoch-caddy"]
