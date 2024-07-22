#!/usr/bin/env bash

# This entry point is for development only.

#  --ssl-keyfile /etc/ssl/private/ssl-cert-snakeoil.key \
#  --ssl-certfile /etc/ssl/certs/ssl-cert-snakeoil.pem

uvicorn main:app \
  --app-dir webapp/ \
  --reload \
  --port 5443 \
  --host 0.0.0.0 \
  --log-level debug \
  --log-config logging.conf \
  --workers 1 \
  --proxy-headers \
  --forwarded-allow-ips '*' \
  --ssl-keyfile ssl-cert-snakeoil.key \
  --ssl-certfile ssl-cert-snakeoil.pem

