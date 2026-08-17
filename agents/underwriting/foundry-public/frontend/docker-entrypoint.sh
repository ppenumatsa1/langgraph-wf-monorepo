#!/usr/bin/env sh
set -eu

case "${NGINX_API_UPSTREAM:-}" in
  http://*|https://*) ;;
  *)
    echo "NGINX_API_UPSTREAM must be an http(s) URL." >&2
    exit 1
    ;;
esac

envsubst '${NGINX_API_UPSTREAM}' \
  </etc/nginx/templates/underwriting.conf.template \
  >/etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
