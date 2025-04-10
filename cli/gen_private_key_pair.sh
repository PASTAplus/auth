#!/usr/bin/env bash

# Generate public and private key pair for ES256 (Elliptic Curve Digital Signature Algorithm using the P-256 curve)

SCRIPT_DIR=$(dirname "$(realpath "$0")")
CERTS_DIR="$SCRIPT_DIR/../certs"
openssl ecparam -genkey -name prime256v1 -noout -out "$CERTS_DIR/private_key.pem"
openssl ec -in "$CERTS_DIR/private_key.pem" -pubout -out "$CERTS_DIR/public_key.pem"
