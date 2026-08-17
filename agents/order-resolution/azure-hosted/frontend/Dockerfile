FROM node:20.19.0-alpine3.20 AS build

WORKDIR /app

COPY package*.json .npmrc ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

USER root
RUN apk add --no-cache gettext

COPY nginx.conf /etc/nginx/conf.d/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
    && chown -R 101:101 /etc/nginx/conf.d /usr/share/nginx/html

USER 101
EXPOSE 5173

ENTRYPOINT ["/docker-entrypoint.sh"]
