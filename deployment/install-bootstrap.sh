#!/usr/bin/env bash

set -e # Exit on error

BOOTSTRAP_SRC='https://github.com/twbs/bootstrap/releases/download/v5.3.8/bootstrap-5.3.8-dist.zip'
BOOTSTRAP_DIR='bootstrap-5.3.8-dist'

ICON_SRC='https://github.com/twbs/icons/releases/download/v1.13.1/bootstrap-icons-1.13.1.zip'
ICON_DIR='bootstrap-icons-1.13.1'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

DST="$PARENT_DIR/webapp/static/bootstrap"
mkdir -p "$DST"

# Sadly, unzip does not support reading from stdin
TMP_DIR="$(mktemp --directory)"
TMP_ZIP="$TMP_DIR/bootstrap.zip"
wget -O "$TMP_ZIP" "$BOOTSTRAP_SRC"
unzip -od "$DST" "$TMP_ZIP"

TMP_ZIP="$TMP_DIR/bootstrap-icons.zip"
wget -O "$TMP_ZIP" "$ICON_SRC"
unzip -od "$DST" "$TMP_ZIP"

ln -rs "$DST/$BOOTSTRAP_DIR" "$DST/bootstrap"
ln -rs "$DST/$ICON_DIR" "$DST/bootstrap-icons"

# We let the temp dir get cleaned up by the OS on next reboot

echo "Bootstrap installed to $DST"
