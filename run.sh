#!/usr/bin/env bash

# This entry point is for development only.

#  --ssl-keyfile /etc/ssl/private/ssl-cert-snakeoil.key
#  --ssl-certfile /etc/ssl/certs/ssl-cert-snakeoil.pem
#  --log-config logging.conf

uvicorn main:app \
  --app-dir webapp \
  --reload \
  --port 5443 \
  --host 0.0.0.0 \
  --log-level debug \
  --workers 4 \
  --proxy-headers \
  --forwarded-allow-ips '*' \
  --ssl-keyfile /home/pasta/certificates/localhost.key \
  --ssl-certfile /home/pasta/certificates/localhost.crt

