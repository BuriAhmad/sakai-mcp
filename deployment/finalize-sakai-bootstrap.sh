#!/usr/bin/env bash
set -Eeuo pipefail

# Run only after the first successful empty-database start has populated the
# Sakai schema and demo data. It makes later starts normal operational starts.
TOMCAT_HOME='/opt/tomcat'

sudo systemctl stop tomcat
sudo sed -i 's/^auto\.ddl=.*/auto.ddl=false/' "$TOMCAT_HOME/sakai/local.properties"
sudo sed -i 's/ -Dsakai.demo=true//g' "$TOMCAT_HOME/bin/setenv.sh"
sudo systemctl start tomcat
