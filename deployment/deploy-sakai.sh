#!/usr/bin/env bash
set -Eeuo pipefail

# Runs on the VM after configure-vm.sh and configure-sakai.sh. Build output is
# deliberately written to /var/log/sakai-build.log for recovery diagnostics.
SOURCE_DIR='/opt/sakai-src'
MAVEN='/opt/maven/bin/mvn'
TOMCAT_HOME='/opt/tomcat'

[[ "$(sudo -u tomcat -H git -C "$SOURCE_DIR" describe --tags --exact-match)" == '25.2' ]] || {
  echo 'Refusing to build: source is not exactly Sakai tag 25.2.' >&2; exit 1;
}
sudo install -d -o tomcat -g tomcat -m 0750 /opt/tomcat/.m2
sudo chown -R tomcat:tomcat "$SOURCE_DIR"
sudo -u tomcat -H env MAVEN_OPTS='-Xms512m -Xmx3072m' \
  "$MAVEN" -B -DskipTests -f "$SOURCE_DIR/master/pom.xml" clean install
sudo -u tomcat -H env MAVEN_OPTS='-Xms512m -Xmx3072m' \
  "$MAVEN" -B -DskipTests -f "$SOURCE_DIR/pom.xml" clean install sakai:deploy \
  -Dmaven.tomcat.home="$TOMCAT_HOME" -Dsakai.home="$TOMCAT_HOME/sakai"

# The JDBC connector is resolved during the source build but must also be on
# Tomcat's shared classpath before its first Sakai startup.
sudo install -o tomcat -g tomcat -m 0640 \
  "$TOMCAT_HOME/.m2/repository/com/mysql/mysql-connector-j/9.0.0/mysql-connector-j-9.0.0.jar" \
  "$TOMCAT_HOME/lib/mysql-connector-j-9.0.0.jar"
sudo ln -sfn serializer-2.7.3.jar "$TOMCAT_HOME/lib/serializer.jar"
# Sakai 25.2's demo Course Management sample loader calls the user directory
# during its init method but does not declare that lifecycle dependency. On a
# fresh database this can run before its storage has initialized.
DEMO_COMPONENT="$TOMCAT_HOME/components/coursemanagement-hibernate-pack/WEB-INF/components-demo.xml"
if ! grep -q 'depends-on="org.sakaiproject.user.api.UserDirectoryService"' "$DEMO_COMPONENT"; then
  sudo sed -i 's#<bean id="org.sakaiproject.coursemanagement.impl.CourseManagementSampleDataLoader"#<bean depends-on="org.sakaiproject.user.api.UserDirectoryService" id="org.sakaiproject.coursemanagement.impl.CourseManagementSampleDataLoader"#' "$DEMO_COMPONENT"
fi
sudo chown -R tomcat:tomcat "$TOMCAT_HOME/webapps" "$TOMCAT_HOME/lib"
sudo systemctl start tomcat
