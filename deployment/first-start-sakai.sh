#!/usr/bin/env bash
set -Eeuo pipefail

# One-time first-start procedure for a fresh Sakai database. This deliberately
# resets only the named Sakai application database; it never changes the MySQL
# server, resource group, or any Azure network resource.
[[ "${SAKAI_RESET_CONFIRM:-}" == "YES" ]] || {
  echo 'Refusing to reset application data. Re-run with SAKAI_RESET_CONFIRM=YES.' >&2
  exit 2
}

TOMCAT_HOME='/opt/tomcat'
LOCAL_PROPERTIES="$TOMCAT_HOME/sakai/local.properties"
INITIALIZER="$(cd "$(dirname "$0")" && pwd)/initialize-sakai-schema.sh"

sudo test -r "$LOCAL_PROPERTIES" || { echo "Missing $LOCAL_PROPERTIES" >&2; exit 1; }
[[ -x "$INITIALIZER" ]] || { echo "Missing executable $INITIALIZER" >&2; exit 1; }

mysql_host=$(sudo sed -n 's#^url@javax\.sql\.BaseDataSource=jdbc:mysql://\([^:/?]*\).*#\1#p' "$LOCAL_PROPERTIES")
mysql_password=$(sudo sed -n 's/^password@javax\.sql\.BaseDataSource=//p' "$LOCAL_PROPERTIES")
[[ -n "$mysql_host" && -n "$mysql_password" ]] || { echo 'Could not read Sakai database connection settings.' >&2; exit 1; }

sudo systemctl stop tomcat
MYSQL_PWD="$mysql_password" mysql \
  --protocol=TCP --ssl-mode=VERIFY_IDENTITY --ssl-ca=/etc/ssl/certs/ca-certificates.crt \
  -h "$mysql_host" -u sakaidb \
  -e 'DROP DATABASE IF EXISTS sakai; CREATE DATABASE sakai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'

MYSQL_HOST="$mysql_host" SAKAI_DB_PASSWORD="$mysql_password" "$INITIALIZER"
sudo systemctl start tomcat
echo 'Fresh Sakai schema installed and Tomcat started in demo initialization mode.'
