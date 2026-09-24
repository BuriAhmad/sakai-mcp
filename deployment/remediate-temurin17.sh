#!/usr/bin/env bash
set -Eeuo pipefail

# Repairs an already-deployed Sakai 25.2 VM that was bootstrapped with a newer
# OpenJDK 17 build. This does not rebuild Sakai or alter its database.
TEMURIN_VERSION='17.0.15_6'
TEMURIN_HOME='/opt/temurin17'
TOMCAT_HOME='/opt/tomcat'

sudo systemctl stop tomcat || true
if ! "$TEMURIN_HOME/bin/java" -version 2>&1 | grep -q '17.0.15'; then
  curl -fsSL "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.15%2B6/OpenJDK17U-jdk_x64_linux_hotspot_17.0.15_6.tar.gz" \
    -o /tmp/temurin17.tar.gz
  sudo rm -rf "/opt/jdk-$TEMURIN_VERSION"
  sudo tar -xzf /tmp/temurin17.tar.gz -C /opt
  sudo mv /opt/jdk-17.0.15+6 "/opt/jdk-$TEMURIN_VERSION"
  sudo ln -sfn "/opt/jdk-$TEMURIN_VERSION" "$TEMURIN_HOME"
fi

sudo sed -i \
  -e 's#^Environment=JAVA_HOME=.*#Environment=JAVA_HOME=/opt/temurin17#' \
  -e 's#^Environment=JRE_HOME=.*#Environment=JRE_HOME=/opt/temurin17#' \
  /etc/systemd/system/tomcat.service
sudo sed -i \
  -e 's#^export JAVA_HOME=.*#export JAVA_HOME=/opt/temurin17#' \
  -e 's#^export JRE_HOME=.*#export JRE_HOME=/opt/temurin17#' \
  /opt/tomcat/bin/setenv.sh
sudo sed -i \
  -e 's#^export CATALINA_OPTS=.*#export CATALINA_OPTS="-server -Xms2048m -Xmx4096m -XX:+UseG1GC -Dfile.encoding=UTF-8 -Djava.awt.headless=true -Djava.net.preferIPv4Stack=true --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/jdk.internal.misc=ALL-UNNAMED --add-opens=java.base/sun.util.calendar=ALL-UNNAMED --add-opens=java.base/jdk.internal.access=ALL-UNNAMED --add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED --add-opens=java.base/sun.security.action=ALL-UNNAMED --add-opens=java.base/sun.security.util=ALL-UNNAMED --add-opens=java.management/com.sun.jmx.mbeanserver=ALL-UNNAMED --add-opens=jdk.internal.jvmstat/sun.jvmstat.monitor=ALL-UNNAMED --add-opens=java.base/sun.reflect.generics.reflectiveObjects=ALL-UNNAMED --add-opens=java.sql/java.sql=ALL-UNNAMED -Dsakai.demo=true"#' \
  /opt/tomcat/bin/setenv.sh
sudo systemctl daemon-reload
"$TEMURIN_HOME/bin/java" -version
"$TEMURIN_HOME/bin/javap" jdk.internal.reflect.ConstructorAccessorImpl >/dev/null
sudo systemctl start tomcat
