#!/usr/bin/env sh
set -eu

: "${NGINX_API_UPSTREAM:?NGINX_API_UPSTREAM must be set to the internal backend URL}"
NGINX_API_UPSTREAM="${NGINX_API_UPSTREAM%/}"
export NGINX_API_UPSTREAM

cp /usr/share/nginx/html/env-config.template.js /usr/share/nginx/html/env-config.js

envsubst '${NGINX_API_UPSTREAM}' \
  < /etc/nginx/conf.d/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
