#!/usr/bin/env bash
set -Eeuo pipefail

# Complete Sakai's own MySQL user-schema script before the first demo start.
# Hibernate may already have created SAKAI_USER_PROPERTY; --force lets the
# upstream script continue past that harmless duplicate-key statement to its
# required SAKAI_USER, ID-map, admin, and postmaster statements.
: "${MYSQL_HOST:?MYSQL_HOST is required}"
: "${SAKAI_DB_PASSWORD:?SAKAI_DB_PASSWORD is required}"

SOURCE_DIR="${SOURCE_DIR:-/opt/sakai-src}"
DDL_FILE="$SOURCE_DIR/kernel/kernel-impl/src/main/sql/mysql/sakai_user.sql"
[[ -r "$DDL_FILE" ]] || { echo "Missing Sakai user DDL: $DDL_FILE" >&2; exit 1; }

MYSQL_PWD="$SAKAI_DB_PASSWORD" mysql \
  --protocol=TCP --ssl-mode=VERIFY_IDENTITY --ssl-ca=/etc/ssl/certs/ca-certificates.crt \
  --force -h "$MYSQL_HOST" -u sakaidb sakai < <(sed '/^---*$/d' "$DDL_FILE")

MYSQL_PWD="$SAKAI_DB_PASSWORD" mysql \
  --protocol=TCP --ssl-mode=VERIFY_IDENTITY --ssl-ca=/etc/ssl/certs/ca-certificates.crt \
  -N -h "$MYSQL_HOST" -u sakaidb sakai \
  -e 'SELECT COUNT(*) FROM SAKAI_USER WHERE USER_ID = "admin";' | grep -qx '1'
