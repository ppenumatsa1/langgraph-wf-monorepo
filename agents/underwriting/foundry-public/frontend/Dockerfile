FROM node:22-bookworm-slim AS build

WORKDIR /app

COPY package*.json .npmrc ./
RUN npm ci --include=dev --no-audit --no-fund

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

RUN apk add --no-cache gettext
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/underwriting.conf.template
COPY docker-entrypoint.sh /usr/local/bin/underwriting-entrypoint
RUN chmod 0755 /usr/local/bin/underwriting-entrypoint

EXPOSE 80

ENTRYPOINT ["/usr/local/bin/underwriting-entrypoint"]
