#!/usr/bin/env bash
set -Eeuo pipefail

# Apply the complete Sakai 25.2 kernel MySQL schema set to a fresh `sakai`
# database. Sakai's auto-DDL invokes these files service-by-service, but with
# MySQL 8 a Hibernate-created table can make an early duplicate-key statement
# stop a file before its later tables are created. Applying the exact upstream
# files in force/continue mode prevents that partial-schema bootstrap state.
: "${MYSQL_HOST:?MYSQL_HOST is required}"
: "${SAKAI_DB_PASSWORD:?SAKAI_DB_PASSWORD is required}"

SOURCE_DIR="${SOURCE_DIR:-/opt/sakai-src}"
SQL_DIR="$SOURCE_DIR/kernel/kernel-impl/src/main/sql/mysql"
[[ -d "$SQL_DIR" ]] || { echo "Missing Sakai MySQL DDL directory: $SQL_DIR" >&2; exit 1; }

while IFS= read -r ddl_file; do
  echo "Applying upstream Sakai DDL: $(basename "$ddl_file")"
  MYSQL_PWD="$SAKAI_DB_PASSWORD" mysql \
    --protocol=TCP --ssl-mode=VERIFY_IDENTITY --ssl-ca=/etc/ssl/certs/ca-certificates.crt \
    --force -h "$MYSQL_HOST" -u sakaidb sakai < <(sed '/^---*$/d' "$ddl_file")
done < <(find "$SQL_DIR" -maxdepth 1 -type f -name '*.sql' -print | sort)

MYSQL_PWD="$SAKAI_DB_PASSWORD" mysql \
  --protocol=TCP --ssl-mode=VERIFY_IDENTITY --ssl-ca=/etc/ssl/certs/ca-certificates.crt \
  -N -h "$MYSQL_HOST" -u sakaidb sakai \
  -e 'SELECT COUNT(*) FROM SAKAI_USER WHERE USER_ID = "admin";' | grep -qx '1'
