#!/usr/bin/env bash
set -Eeuo pipefail

# Runs on the Sakai VM as its SSH administrator. It is safe to rerun.
SUDO='sudo'
TOMCAT_VERSION='9.0.121'
MAVEN_VERSION='3.9.16'
TEMURIN_VERSION='17.0.15_6'
TEMURIN_HOME='/opt/temurin17'
TOMCAT_USER='tomcat'
TOMCAT_HOME='/opt/tomcat'

$SUDO apt-get update
$SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ca-certificates curl git gnupg jq less mysql-client netcat-openbsd \
  unzip zip build-essential openssl nginx certbot python3-certbot-nginx \
  fontconfig

# Sakai 25 was QA-tested with Temurin 17.0.15.  Later OpenJDK 17 updates can
# remove legacy internal reflection classes still used by Sakai SiteStats.
if ! "$TEMURIN_HOME/bin/java" -version 2>&1 | grep -q '17.0.15'; then
  curl -fsSL "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.15%2B6/OpenJDK17U-jdk_x64_linux_hotspot_17.0.15_6.tar.gz" \
    -o /tmp/temurin17.tar.gz
  $SUDO rm -rf "/opt/jdk-$TEMURIN_VERSION"
  $SUDO tar -xzf /tmp/temurin17.tar.gz -C /opt
  $SUDO mv /opt/jdk-17.0.15+6 "/opt/jdk-$TEMURIN_VERSION"
  $SUDO ln -sfn "/opt/jdk-$TEMURIN_VERSION" "$TEMURIN_HOME"
fi

if ! command -v mvn >/dev/null 2>&1 || ! mvn --version | head -1 | grep -q "Apache Maven $MAVEN_VERSION"; then
  curl -fsSL "https://dlcdn.apache.org/maven/maven-3/$MAVEN_VERSION/binaries/apache-maven-$MAVEN_VERSION-bin.tar.gz" \
    -o /tmp/apache-maven.tar.gz
  $SUDO rm -rf "/opt/apache-maven-$MAVEN_VERSION"
  $SUDO tar -xzf /tmp/apache-maven.tar.gz -C /opt
  $SUDO ln -sfn "/opt/apache-maven-$MAVEN_VERSION" /opt/maven
  $SUDO tee /etc/profile.d/maven.sh >/dev/null <<'EOF'
export MAVEN_HOME=/opt/maven
export PATH="$MAVEN_HOME/bin:$PATH"
EOF
fi
export PATH="/opt/maven/bin:$PATH"

if ! id -u "$TOMCAT_USER" >/dev/null 2>&1; then
  $SUDO useradd --system --home-dir "$TOMCAT_HOME" --shell /usr/sbin/nologin "$TOMCAT_USER"
fi
if ! $SUDO test -x "$TOMCAT_HOME/bin/catalina.sh"; then
  curl -fsSL "https://dlcdn.apache.org/tomcat/tomcat-9/v$TOMCAT_VERSION/bin/apache-tomcat-$TOMCAT_VERSION.tar.gz" \
    -o /tmp/apache-tomcat.tar.gz
  $SUDO rm -rf "$TOMCAT_HOME" "/opt/apache-tomcat-$TOMCAT_VERSION"
  $SUDO tar -xzf /tmp/apache-tomcat.tar.gz -C /opt
  $SUDO mv "/opt/apache-tomcat-$TOMCAT_VERSION" "$TOMCAT_HOME"
fi
# Remove only the stock Tomcat applications. Do not wipe this directory on a
# rerun: it may already contain a working Sakai deployment.
$SUDO rm -rf "$TOMCAT_HOME/webapps/ROOT" "$TOMCAT_HOME/webapps/docs" \
  "$TOMCAT_HOME/webapps/examples" "$TOMCAT_HOME/webapps/manager" \
  "$TOMCAT_HOME/webapps/host-manager"
$SUDO find "$TOMCAT_HOME/bin" -maxdepth 1 -type f -name '*.sh' -exec chmod 0750 {} +
# Sakai needs the JDBC driver in Tomcat's shared classpath. The source build
# resolves this exact modern MySQL Connector/J artifact into Tomcat's Maven repo.
if [[ -f "$TOMCAT_HOME/.m2/repository/com/mysql/mysql-connector-j/9.0.0/mysql-connector-j-9.0.0.jar" ]]; then
  $SUDO install -o "$TOMCAT_USER" -g "$TOMCAT_USER" -m 0640 \
    "$TOMCAT_HOME/.m2/repository/com/mysql/mysql-connector-j/9.0.0/mysql-connector-j-9.0.0.jar" \
    "$TOMCAT_HOME/lib/mysql-connector-j-9.0.0.jar"
fi
$SUDO install -d -o "$TOMCAT_USER" -g "$TOMCAT_USER" -m 0750 "$TOMCAT_HOME/sakai" "$TOMCAT_HOME/logs"
$SUDO chown -R "$TOMCAT_USER:$TOMCAT_USER" "$TOMCAT_HOME"

$SUDO tee "$TOMCAT_HOME/bin/setenv.sh" >/dev/null <<'EOF'
export CATALINA_HOME=/opt/tomcat
export CATALINA_BASE=/opt/tomcat
export JAVA_HOME=/opt/temurin17
export JRE_HOME=/opt/temurin17
export CATALINA_OPTS="-server -Xms2048m -Xmx4096m -XX:+UseG1GC -Dfile.encoding=UTF-8 -Djava.awt.headless=true -Djava.net.preferIPv4Stack=true --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/jdk.internal.misc=ALL-UNNAMED --add-opens=java.base/sun.util.calendar=ALL-UNNAMED --add-opens=java.base/jdk.internal.access=ALL-UNNAMED --add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED --add-opens=java.base/sun.security.action=ALL-UNNAMED --add-opens=java.base/sun.security.util=ALL-UNNAMED --add-opens=java.management/com.sun.jmx.mbeanserver=ALL-UNNAMED --add-opens=jdk.internal.jvmstat/sun.jvmstat.monitor=ALL-UNNAMED --add-opens=java.base/sun.reflect.generics.reflectiveObjects=ALL-UNNAMED --add-opens=java.sql/java.sql=ALL-UNNAMED -Dsakai.demo=true"
export JAVA_OPTS="-Dfile.encoding=UTF-8 -Djava.awt.headless=true"
EOF
$SUDO chmod 0750 "$TOMCAT_HOME/bin/setenv.sh"
$SUDO chown "$TOMCAT_USER:$TOMCAT_USER" "$TOMCAT_HOME/bin/setenv.sh"

$SUDO sed -i 's/port="8080" protocol="HTTP\/1.1"/port="8080" protocol="HTTP\/1.1" URIEncoding="UTF-8"/' "$TOMCAT_HOME/conf/server.xml"
$SUDO tee /etc/systemd/system/tomcat.service >/dev/null <<'EOF'
[Unit]
Description=Apache Tomcat 9 serving Sakai
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
User=tomcat
Group=tomcat
Environment=CATALINA_HOME=/opt/tomcat
Environment=CATALINA_BASE=/opt/tomcat
Environment=CATALINA_PID=/opt/tomcat/temp/tomcat.pid
Environment=JAVA_HOME=/opt/temurin17
Environment=JRE_HOME=/opt/temurin17
ExecStart=/opt/tomcat/bin/startup.sh
ExecStop=/opt/tomcat/bin/shutdown.sh
SuccessExitStatus=143
Restart=on-failure
RestartSec=15
UMask=0027

[Install]
WantedBy=multi-user.target
EOF
$SUDO systemctl daemon-reload
$SUDO systemctl enable tomcat

"$TEMURIN_HOME/bin/java" -version
mvn --version
git --version
$SUDO "$TOMCAT_HOME/bin/version.sh"
df -h /
free -h
